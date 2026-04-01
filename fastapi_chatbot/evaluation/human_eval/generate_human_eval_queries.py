#!/usr/bin/env python
"""Generate multilingual human-evaluation queries from PostgreSQL.

Creates 100 prompts total:
- 50 legal_query prompts (targeting legal RAG collection)
- 50 conceptual_question prompts (targeting NLP knowledge RAG collection)

Languages are intentionally mixed across Arabic/French/English/code-mixed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_DB_URL = "postgresql+asyncpg://nlp_admin:changeme123@db:5432/nlp_platform"

LANG_SCHEDULE = [
    "ar",
    "fr",
    "en",
    "ar",
    "fr",
    "en",
    "mix",
    "ar",
    "fr",
    "en",
]

LEGAL_TEMPLATES: dict[str, list[str]] = {
    "ar": [
        "قضية عملية: شركة لم تلتزم ببند مذكور في {title}. ما المخالفة المحتملة وما الآثار القانونية الأساسية؟",
        "نزاع أمام المحكمة: طرفان يختلفان حول تطبيق مادة من {title}. ما الوقائع التي يجب على القاضي التحقق منها قبل الحكم؟",
        "محضر قانوني: استخرج من {title} الشروط الشكلية والإجرائية التي إذا غابت قد تبطل الإجراء.",
        "سيناريو تعاقدي: بناءً على {title}، ما العناصر الإلزامية التي يجب إثباتها لقبول الدعوى؟",
        "في ملف نزاع مدني مرتبط بـ {title}، ما الدفوع الأقوى للمدعي وما الردود المتوقعة من المدعى عليه؟",
        "حلّل حالة خرق التزام وارد في {title}: ما التسلسل المنطقي من إثبات الواقعة إلى تحديد الجزاء؟",
        "إذا تعارض تفسيرين لنص في {title}، كيف يفصل القاضي بين التفسير الضيق والتفسير الموسع؟",
        "ملف امتثال: ما الإجراءات الوقائية التي ينبغي للمؤسسة اتخاذها لتجنب مسؤولية قانونية وفق {title}؟",
        "سؤال إثبات: في ضوء {title}، ما نوع الأدلة الأكثر حسماً لإثبات العلاقة القانونية محل النزاع؟",
        "في واقعة مشابهة لما ورد في {title}، متى يكون اللجوء للتسوية أفضل من التقاضي ولماذا قانونياً؟",
    ],
    "fr": [
        "Cas pratique: une entreprise n'a pas respecte une obligation citee dans {title}. Quelle qualification juridique et quelles consequences probables?",
        "Litige devant le juge: deux interpretations d'un article de {title} s'opposent. Quels criteres de preuve faut-il prioriser?",
        "Memo juridique: a partir de {title}, identifie les conditions de recevabilite de l'action et les causes d'irrecevabilite.",
        "Scenario contractuel fonde sur {title}: quels elements doivent etre etablis pour engager la responsabilite?",
        "Dans un contentieux inspire de {title}, propose la strategie du demandeur puis la defense la plus solide du defendeur.",
        "Analyse procedurale: selon {title}, quelles etapes sont obligatoires avant de saisir la juridiction competente?",
        "Conflit d'interpretation de {title}: quand appliquer une lecture stricte et quand une lecture teleologique?",
        "Audit de conformite: quelles mesures internes minimisent le risque de sanction au regard de {title}?",
        "Question de preuve: pour un dossier lie a {title}, quelles pieces documentaires ont la plus forte valeur probante?",
        "Dans un cas similaire a {title}, quand recommander une transaction plutot qu'un proces, et sur quelle base juridique?",
    ],
    "en": [
        "Case scenario: a company breaches an obligation referenced in {title}. What is the likely legal characterization and immediate consequence?",
        "Courtroom dispute: two parties rely on conflicting readings of {title}. Which factual elements should the judge verify first?",
        "Draft a legal memo from {title}: list admissibility conditions and common grounds for dismissal.",
        "Contract liability question based on {title}: what must be proven to establish liability and causation?",
        "For a dispute aligned with {title}, provide the claimant's strongest argument and the respondent's best counter-argument.",
        "Procedural path analysis: under {title}, what sequence of steps is mandatory before filing a claim?",
        "Interpretation conflict in {title}: when should a strict interpretation prevail over a purposive interpretation?",
        "Compliance briefing: what preventive controls should an organization implement to reduce sanctions risk under {title}?",
        "Evidence strategy: in a case tied to {title}, which forms of evidence are most persuasive and why?",
        "In a {title}-style dispute, when is settlement legally preferable to litigation?",
    ],
    "mix": [
        "Case file from {title}: شكون عندو burden of proof first, and what evidence is decisive?",
        "Dans un conflit base sur {title}, عطيني claimant strategy + strongest defense in one structured answer.",
        "For compliance under {title}, شنو mandatory steps before court filing and where do parties usually fail?",
        "From {title}, build a judge-style reasoning path: facts -> legal rule -> application -> decision.",
        "Litigation or settlement for a {title} dispute: donne-moi legal criteria + practical risk factors.",
        "In {title}, si deux interpretations clash, كيفاش نختار the legally safer interpretation?",
    ],
}

NLP_TEMPLATES: dict[str, list[str]] = {
    "ar": [
        "بناءً على {topic}، اقترح تجربة تقييم واقعية وحدد المقاييس المناسبة ولماذا.",
        "في مشروع إنتاجي مرتبط بـ {topic}، ما أكبر مصدرين للانحياز وكيف نرصد كل واحد؟",
        "لدى نموذج مستند إلى {topic} أخطاء متكررة. صمّم خطة تشخيص من 4 خطوات قابلة للتنفيذ.",
        "إذا كانت البيانات قليلة في سيناريو {topic}، ما استراتيجية الضبط الدقيق الأنسب مع تبرير عملي؟",
        "حوّل فكرة {topic} إلى خط أنابيب Production: ingestion -> training -> monitoring -> retraining.",
        "في حالة multilingual حول {topic}، ما الفرق بين الحل الموحد والحلول الخاصة بكل لغة؟",
        "للاستخدام القانوني مع {topic}، ما ضوابط السلامة اللازمة لتقليل الهلوسة والاستشهاد الخاطئ؟",
        "قارن بين نهجين محتملين في {topic} وحدد متى يفشل كل نهج على بيانات عربية.",
        "صمّم protocol تجريبي لـ {topic} يضمن قابلية إعادة النتائج ويكشف data leakage.",
        "إذا انخفض الأداء بعد النشر في نظام يعتمد {topic}، ما إنذارات المراقبة التي يجب تفعيلها فوراً؟",
    ],
    "fr": [
        "A partir de {topic}, propose un protocole d'evaluation robuste avec metriques et seuils d'acceptation.",
        "Pour un systeme base sur {topic}, quels biais principaux doivent etre testes avant mise en production?",
        "Un modele inspire de {topic} degrade en production: donne une procedure de diagnostic en 4 etapes.",
        "Si les donnees sont limitees pour {topic}, quelle strategie de fine-tuning recommandes-tu et pourquoi?",
        "Traduis {topic} en pipeline MLOps complet: collecte, entrainement, validation, monitoring, retrain.",
        "Dans un contexte multilingue autour de {topic}, quand preferer un modele unique vs specialise par langue?",
        "Pour un usage juridique de {topic}, quelles garde-fous reduisent hallucinations et citations faibles?",
        "Compare deux approches concurrentes pour {topic} et precise les conditions d'echec de chacune.",
        "Construis une grille d'ablation pour {topic} afin d'isoler l'impact de chaque composant.",
        "Si la latence explose sur un service base sur {topic}, quelles optimisations prioriser sans perdre en qualite?",
    ],
    "en": [
        "Using {topic}, design a realistic evaluation plan with metrics, baselines, and pass/fail criteria.",
        "For a production system based on {topic}, what are the top bias risks and how would you test each one?",
        "A model influenced by {topic} is failing on edge cases. Provide a 4-step debugging workflow.",
        "If training data is limited for {topic}, which adaptation strategy is most practical and why?",
        "Convert {topic} into an end-to-end MLOps pipeline from ingestion to monitoring and retraining.",
        "In a multilingual setup using {topic}, when should you choose one shared model vs language-specific models?",
        "For legal-domain deployment with {topic}, which safeguards reduce hallucinations and weak citations?",
        "Compare two competing methods for {topic} and state where each is likely to break.",
        "Create an ablation study design for {topic} that can isolate component-level impact.",
        "If latency spikes in a service built on {topic}, what optimization sequence would you apply first?",
    ],
    "mix": [
        "For {topic}, build a practical test plan: metrics شنو, thresholds combien, and failure cases كيفاش؟",
        "Model based on {topic} is unstable in prod: donne diagnostic steps + quick wins for recovery.",
        "Avec {topic}, واش mieux one multilingual model ولا per-language models? justify with trade-offs.",
        "From {topic}, propose anti-hallucination guardrails for legal QA and explain why each guardrail matters.",
        "If latency is high with {topic}, عطيني prioritized optimization roadmap without hurting quality.",
        "Using {topic}, fais une ablation matrix and specify which component to remove first and why.",
    ],
}

LEGAL_CASE_FACTS = {
    "ar": [
        "المدعي يطالب بالتعويض بعد إخلال تعاقدي موثق بمراسلات رسمية",
        "المدعى عليه يتمسك بعدم الاختصاص النوعي للمحكمة",
        "يوجد شرط جزائي محل نزاع حول تطبيقه وحدوده",
        "أحد الأطراف يدفع ببطلان الإجراء لعيب شكلي",
        "الوقائع تتضمن تأخيراً متكرراً في تنفيذ التزام جوهري",
    ],
    "fr": [
        "le demandeur sollicite des dommages-interets apres une inexécution contractuelle documentee",
        "le defendeur invoque l'incompetence de la juridiction saisie",
        "une clause penale est contestee quant a sa portee",
        "une partie souleve une nullite pour vice de forme",
        "le dossier montre des retards repetes sur une obligation essentielle",
    ],
    "en": [
        "the claimant seeks damages after documented contractual non-performance",
        "the respondent challenges the court's subject-matter jurisdiction",
        "a penalty clause is disputed as to scope and enforceability",
        "one party alleges procedural nullity due to a formal defect",
        "the record shows repeated delay on a core obligation",
    ],
    "mix": [
        "claimant kaytleb damages after breach documented b emails",
        "defender kaygol court maandhach jurisdiction on this dispute",
        "clause pénale disputed and parties disagree on execution threshold",
        "wahed taraf kaydefa3 b nullité procédurale cause form defects",
        "timeline shows repeated delays on obligation principale",
    ],
}

LEGAL_TASKS = {
    "ar": [
        "رتّب حيثيات الحكم: الوقائع، التكييف، التعليل، والمنطوق",
        "حدّد ما يجب إثباته أولاً ومن يتحمل عبء الإثبات في كل نقطة",
        "ابنِ مذكرة قضائية مختصرة تتضمن أقوى دفعين لكل طرف",
        "استخرج شروط القبول الشكلي قبل الدخول في الموضوع",
        "ضع مسار قرار القاضي عند تعارض تفسيرين للنص",
    ],
    "fr": [
        "structure le raisonnement du juge: faits, qualification, motivation, dispositif",
        "indique l'ordre des preuves et la charge de la preuve par point",
        "redige une note contentieuse avec deux moyens forts par partie",
        "isole les conditions de recevabilite avant examen au fond",
        "trace la methode de decision en cas de conflit d'interpretation",
    ],
    "en": [
        "structure a judge-ready analysis: facts, qualification, reasoning, holding",
        "set the proof order and burden of proof for each contested element",
        "draft a concise litigation memo with two strongest arguments per side",
        "separate admissibility checks from merits analysis",
        "map the decision path when two interpretations of the text conflict",
    ],
    "mix": [
        "build juge-style reasoning: facts -> qualification -> motivation -> decision",
        "حدد burden of proof for each disputed element and why",
        "prepare short memo: strongest argument dial claimant + best defense",
        "before merits, sort admissibility conditions واحد بواحد",
        "if interpretations clash, give legally safer decision path",
    ],
}

NLP_SCENARIOS = {
    "ar": [
        "نظام استرجاع معرفي عربي في بيئة إنتاجية",
        "تصنيف نصوص قانونية متعددة اللهجات",
        "مساعد إجابة يعتمد RAG مع متطلبات تدقيق عالية",
        "اكتشاف الكيانات في وثائق طويلة غير متوازنة",
        "تقييم نموذج متعدد اللغات تحت قيود زمن استجابة صارمة",
    ],
    "fr": [
        "pipeline RAG juridique arabe deploye en production",
        "classification de textes juridiques multi-dialectes",
        "assistant QA avec exigences fortes de tracabilite",
        "reconnaissance d'entites sur documents longs desequilibres",
        "modele multilingue avec contrainte severe de latence",
    ],
    "en": [
        "Arabic legal RAG system running in production",
        "multi-dialect legal text classification workload",
        "high-stakes QA assistant with strict auditability",
        "entity extraction over long, imbalanced documents",
        "multilingual model under strict latency constraints",
    ],
    "mix": [
        "prod RAG juridique arabe with strict reliability KPIs",
        "classification légal multi-dialect with noisy labels",
        "QA assistant where citation quality is mission-critical",
        "NER on long docs with class imbalance كبير",
        "multilingual inference with hard latency budget",
    ],
}

NLP_TASKS = {
    "ar": [
        "اقترح خطة تقييم بمؤشرات دقيقة وحدود قبول رقمية",
        "حدّد أعطال الإنتاج المتوقعة وآلية إنذار مبكر لكل عطل",
        "صمّم تجارب ablation تكشف مساهمة كل مكون",
        "قدّم خطة تقليل الهلوسة مع آلية تحقق من الاستشهادات",
        "ضع خطة تحسين أداء دون التضحية بالدقة",
    ],
    "fr": [
        "propose un plan d'evaluation avec metriques et seuils numeriques",
        "liste les pannes de production probables et les alertes associees",
        "construis une campagne d'ablation pour mesurer chaque composant",
        "definis des garde-fous anti-hallucination avec verification des citations",
        "etablis un plan d'optimisation performance sans perte de precision",
    ],
    "en": [
        "propose an evaluation protocol with numeric acceptance thresholds",
        "identify likely production failures and early-warning signals",
        "design an ablation campaign to isolate component contribution",
        "define anti-hallucination safeguards with citation verification",
        "build a performance optimization plan without accuracy collapse",
    ],
    "mix": [
        "build eval protocol with metrics واضحة and numeric thresholds",
        "list top prod failures and alerting signals خطوة بخطوة",
        "design ablation matrix to isolate each component impact",
        "define anti-hallucination guardrails + citation checks robustes",
        "optimize latency first without breaking quality baselines",
    ],
}


@dataclass
class SourceRow:
    doc_id: int
    language: str | None
    title_or_topic: str
    content: str


def excerpt(text: str, max_words: int = 14) -> str:
    words = [w for w in (text or "").replace("\n", " ").split() if w.strip()]
    if not words:
        return ""
    return " ".join(words[:max_words])


def pick_language(i: int) -> str:
    return LANG_SCHEDULE[i % len(LANG_SCHEDULE)]


def pick_template(templates: dict[str, list[str]], lang: str, i: int) -> str:
    choices = templates.get(lang) or templates["en"]
    return choices[i % len(choices)]


def _pick_variant(options: dict[str, list[str]], lang: str, i: int, key: str) -> str:
    pool = options.get(lang) or options["en"]
    digest = hashlib.sha1(f"{lang}|{i}|{key}".encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(pool)
    return pool[idx]


def _dedupe_variant(base: str, seen: set[str], suffix_seed: str) -> str:
    text = base.strip()
    if text not in seen:
        seen.add(text)
        return text
    h = hashlib.sha1(suffix_seed.encode("utf-8")).hexdigest()[:6]
    alt = f"{text} [variant:{h}]"
    seen.add(alt)
    return alt


async def fetch_sources(
    db_url: str,
    legal_pool: int,
    nlp_pool: int,
) -> tuple[list[SourceRow], list[SourceRow]]:
    engine = create_async_engine(db_url, future=True)
    async with engine.connect() as conn:
        legal_rs = await conn.execute(
            text(
                """
                SELECT id, language, title
                     , content
                FROM legal_documents
                WHERE title IS NOT NULL AND content IS NOT NULL
                ORDER BY id
                LIMIT :lim
                """
            ),
            {"lim": legal_pool},
        )
        legal_rows = [
            SourceRow(
                doc_id=int(r._mapping["id"]),
                language=r._mapping.get("language"),
                title_or_topic=str(r._mapping.get("title") or "Untitled legal document"),
                content=str(r._mapping.get("content") or ""),
            )
            for r in legal_rs
        ]

        nlp_rs = await conn.execute(
            text(
                """
                SELECT id, language, topic
                     , content
                FROM nlp_knowledge
                WHERE topic IS NOT NULL AND content IS NOT NULL
                ORDER BY id
                LIMIT :lim
                """
            ),
            {"lim": nlp_pool},
        )
        nlp_rows = [
            SourceRow(
                doc_id=int(r._mapping["id"]),
                language=r._mapping.get("language"),
                title_or_topic=str(r._mapping.get("topic") or "NLP topic"),
                content=str(r._mapping.get("content") or ""),
            )
            for r in nlp_rs
        ]

    await engine.dispose()
    return legal_rows, nlp_rows


def build_queries(
    legal_rows: list[SourceRow],
    nlp_rows: list[SourceRow],
    legal_count: int,
    nlp_count: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)

    if len(legal_rows) < legal_count:
        raise ValueError(
            f"Not enough legal rows to build {legal_count} prompts. Available={len(legal_rows)}"
        )
    if len(nlp_rows) < nlp_count:
        raise ValueError(
            f"Not enough NLP rows to build {nlp_count} prompts. Available={len(nlp_rows)}"
        )

    legal_sample = rng.sample(legal_rows, legal_count)
    nlp_sample = rng.sample(nlp_rows, nlp_count)

    out: list[dict[str, Any]] = []
    seen_queries: set[str] = set()

    for i, row in enumerate(legal_sample):
        q_lang = pick_language(i)
        template = pick_template(LEGAL_TEMPLATES, q_lang, i)
        ex = excerpt(row.content)
        grounded = f"{row.title_or_topic} :: {ex}" if ex else row.title_or_topic
        fact = _pick_variant(LEGAL_CASE_FACTS, q_lang, i, str(row.doc_id))
        task = _pick_variant(LEGAL_TASKS, q_lang, i, grounded)
        query = template.format(title=grounded)
        query = f"{query} Facts: {fact}. Task: {task}."
        query = _dedupe_variant(query, seen_queries, f"legal|{i}|{row.doc_id}")
        out.append(
            {
                "id": f"LEGAL_{i+1:03d}",
                "domain": "legal",
                "intent": "legal_query",
                "query_language": q_lang,
                "source_row_language": row.language or "unknown",
                "source_document_id": row.doc_id,
                "source_title": row.title_or_topic,
                "query": query,
            }
        )

    for j, row in enumerate(nlp_sample):
        q_lang = pick_language(j)
        template = pick_template(NLP_TEMPLATES, q_lang, j)
        ex = excerpt(row.content)
        grounded = f"{row.title_or_topic} :: {ex}" if ex else row.title_or_topic
        scenario = _pick_variant(NLP_SCENARIOS, q_lang, j, str(row.doc_id))
        task = _pick_variant(NLP_TASKS, q_lang, j, grounded)
        query = template.format(topic=grounded)
        query = f"{query} Scenario: {scenario}. Task: {task}."
        query = _dedupe_variant(query, seen_queries, f"nlp|{j}|{row.doc_id}")
        out.append(
            {
                "id": f"NLP_{j+1:03d}",
                "domain": "nlp",
                "intent": "conceptual_question",
                "query_language": q_lang,
                "source_row_language": row.language or "unknown",
                "source_document_id": row.doc_id,
                "source_title": row.title_or_topic,
                "query": query,
            }
        )

    return out


async def main_async(args: argparse.Namespace) -> None:
    db_url = args.db_url or os.getenv("DATABASE_URL") or DEFAULT_DB_URL
    legal_rows, nlp_rows = await fetch_sources(
        db_url=db_url,
        legal_pool=args.legal_pool,
        nlp_pool=args.nlp_pool,
    )

    rows = build_queries(
        legal_rows=legal_rows,
        nlp_rows=nlp_rows,
        legal_count=args.legal_count,
        nlp_count=args.nlp_count,
        seed=args.seed,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"Generated {len(rows)} human-eval queries "
        f"(legal={args.legal_count}, nlp={args.nlp_count}) -> {output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 100 multilingual human-eval queries")
    parser.add_argument("--output", default="evaluation/human_eval/human_eval_queries.json")
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--legal-count", type=int, default=50)
    parser.add_argument("--nlp-count", type=int, default=50)
    parser.add_argument("--legal-pool", type=int, default=600)
    parser.add_argument("--nlp-pool", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
