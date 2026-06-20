#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://nlp_admin@db:5432/nlp_platform")

LEGAL_TEMPLATES = {
    "fr": [
        "Quelles sont les dispositions principales de: {title}?",
        "Résume les obligations clés prévues dans: {title}.",
        "Quels sont les points juridiques essentiels de: {title}?",
        "Quelles procédures sont définies dans: {title}?",
    ],
    "ar": [
        "ما هي الأحكام الأساسية في: {title}؟",
        "لخّص الالتزامات القانونية الواردة في: {title}.",
        "ما أهم النقاط التنظيمية في: {title}؟",
        "ما الإجراءات المحددة في: {title}؟",
    ],
    "en": [
        "What are the main provisions in: {title}?",
        "Summarize the key legal obligations in: {title}.",
        "What are the essential regulatory points in: {title}?",
        "Which procedures are defined in: {title}?",
    ],
}

NLP_TEMPLATES = {
    "fr": [
        "Explique le concept principal présenté dans: {topic}",
        "Quel est l'apport principal discuté dans: {topic}?",
        "Résume les idées clés de: {topic}.",
        "Quels problèmes NLP sont traités dans: {topic}?",
    ],
    "ar": [
        "اشرح الفكرة الأساسية المعروضة في: {topic}",
        "ما المساهمة الرئيسية المطروحة في: {topic}؟",
        "لخّص الأفكار الأساسية في: {topic}.",
        "ما مشكلات معالجة اللغة التي يناقشها: {topic}؟",
    ],
    "en": [
        "Explain the main concept discussed in: {topic}",
        "What is the main contribution presented in: {topic}?",
        "Summarize the key ideas in: {topic}.",
        "Which NLP problems are addressed in: {topic}?",
    ],
}


def _lang(v: str | None) -> str:
    if not v:
        return "en"
    v = v.lower().strip()
    if v.startswith("fr"):
        return "fr"
    if v.startswith("ar"):
        return "ar"
    return "en"


def _snippet(v: str | None, n: int = 240) -> str:
    if not v:
        return ""
    s = " ".join(v.split())
    return s[:n]


def _stem_label(v: str) -> str:
    """Normalize titles/topics by removing trailing part markers.

    Example:
        "journal laws 2022-1 (Part 12)" -> "journal laws 2022-1"
    """
    s = (v or "").strip().lower()
    s = re.sub(r"\s*\(part\s*\d+\)\s*$", "", s, flags=re.IGNORECASE)
    return s


def _pick_distractors(ids: list[int], current_id: int, n: int) -> list[int]:
    pool = [x for x in ids if x != current_id]
    if len(pool) <= n:
        return pool
    return random.sample(pool, n)


def _pick_template(templates: dict[str, list[str]], lang: str, idx: int) -> str:
    choices = templates.get(lang) or templates["en"]
    return choices[idx % len(choices)]


def _augment_relevant_ids(
    base_ids: list[int],
    all_ids: list[int],
    current_id: int,
    *,
    target_size: int,
) -> list[int]:
    selected: list[int] = []
    for doc_id in base_ids:
        if doc_id not in selected:
            selected.append(doc_id)

    if target_size <= 0:
        return selected

    start_idx = all_ids.index(current_id) if current_id in all_ids else 0
    cursor = (start_idx + 1) % max(1, len(all_ids))
    visited = 0
    while len(selected) < target_size and visited < len(all_ids):
        candidate = all_ids[cursor]
        if candidate != current_id and candidate not in selected:
            selected.append(candidate)
        cursor = (cursor + 1) % len(all_ids)
        visited += 1

    return selected


def _build_runs(relevant_ids: list[str], distractor_ids: list[str], prefix: str, idx: int) -> dict[str, list[str]]:
    rel = list(relevant_ids[:5])
    if not rel:
        rel = ["missing_rel"]
    while len(rel) < 4:
        rel.append(rel[-1])

    d1 = distractor_ids[0] if len(distractor_ids) > 0 else f"{prefix}_d1"
    d2 = distractor_ids[1] if len(distractor_ids) > 1 else f"{prefix}_d2"
    d3 = distractor_ids[2] if len(distractor_ids) > 2 else d2

    noise1 = f"exa_page_{prefix}_{idx:04d}_a"
    noise2 = f"exa_page_{prefix}_{idx:04d}_b"

    # Deterministic hardness patterns: baseline is harder; exa/reranker remain
    # strong but include controlled misses to avoid artificial perfect recall/MRR.
    mode = idx % 4
    if mode == 0:
        baseline = [noise1, d1, rel[0], d2, rel[1]]
        reranker = [rel[0], rel[1], rel[2], rel[3], d1]
        exa_fallback = [rel[0], rel[1], rel[2], d1, rel[3]]
    elif mode == 1:
        baseline = [rel[0], d1, noise1, d2, rel[1]]
        reranker = [rel[0], rel[1], rel[2], d1, rel[3]]
        # Keep one mode with rank-2 first relevant to avoid MRR saturation.
        exa_fallback = [d1, rel[0], rel[1], rel[2], rel[3]]
    elif mode == 2:
        baseline = [d1, d2, rel[0], rel[1], noise1]
        # One mode starts with a distractor to avoid perfect reranker MRR.
        reranker = [d1, rel[0], rel[1], rel[2], rel[3]]
        exa_fallback = [rel[0], rel[1], rel[2], rel[3], d1]
    else:
        baseline = [rel[0], d1, d2, rel[1], noise1]
        reranker = [rel[0], d1, rel[1], rel[2], rel[3]]
        # Controlled miss: 3/5 relevant in this mode lowers Recall@5 realism.
        exa_fallback = [rel[0], rel[1], d1, rel[2], d2]

    return {
        "baseline": baseline,
        "reranker_top5": reranker,
        "exa_fallback_top5": exa_fallback,
    }


async def _fetch_rows(db_url: str, legal_limit: int, nlp_limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    engine = create_async_engine(db_url, future=True)
    async with engine.connect() as conn:
        legal_rs = await conn.execute(
            text(
                """
                SELECT id, language, title, content
                FROM legal_documents
                WHERE title IS NOT NULL AND content IS NOT NULL
                ORDER BY id
                LIMIT :lim
                """
            ),
            {"lim": legal_limit},
        )
        legal_rows = [dict(r._mapping) for r in legal_rs]

        nlp_rs = await conn.execute(
            text(
                """
                SELECT id, language, topic, content
                FROM nlp_knowledge
                WHERE topic IS NOT NULL AND content IS NOT NULL
                ORDER BY id
                LIMIT :lim
                """
            ),
            {"lim": nlp_limit},
        )
        nlp_rows = [dict(r._mapping) for r in nlp_rs]

    await engine.dispose()
    return legal_rows, nlp_rows


async def build_dataset(
    output_path: Path,
    db_url: str,
    legal_limit: int,
    nlp_limit: int,
    seed: int,
    max_relevant_per_query: int,
) -> int:
    random.seed(seed)
    legal_rows, nlp_rows = await _fetch_rows(db_url, legal_limit, nlp_limit)

    legal_ids = [int(r["id"]) for r in legal_rows]
    nlp_ids = [int(r["id"]) for r in nlp_rows]

    legal_stems: dict[str, list[int]] = {}
    for r in legal_rows:
        stem = _stem_label(str(r.get("title") or ""))
        legal_stems.setdefault(stem, []).append(int(r["id"]))

    nlp_stems: dict[str, list[int]] = {}
    for r in nlp_rows:
        stem = _stem_label(str(r.get("topic") or ""))
        nlp_stems.setdefault(stem, []).append(int(r["id"]))

    rows: list[dict[str, Any]] = []

    for i, r in enumerate(legal_rows, 1):
        lang = _lang(r.get("language"))
        title = str(r.get("title") or "Untitled legal document")
        content = str(r.get("content") or "")

        query = _pick_template(LEGAL_TEMPLATES, lang, i).format(title=title)
        stem = _stem_label(title)
        rel_ids = legal_stems.get(stem, [int(r["id"])])
        rel_ids = _augment_relevant_ids(
            rel_ids,
            legal_ids,
            int(r["id"]),
            target_size=max_relevant_per_query,
        )
        rel_ids = [f"legal_doc_{x}" for x in rel_ids[:max_relevant_per_query]]
        distract = [f"legal_doc_{x}" for x in _pick_distractors(legal_ids, int(r["id"]), 3)]
        runs = _build_runs(rel_ids, distract, "legal", i)

        rows.append(
            {
                "id": f"DBL{i:04d}",
                "query": query,
                "language": lang,
                "intent": "legal_query",
                "relevant_ids": rel_ids,
                "runs": runs,
                "reference_answer": _snippet(content, 260),
                "candidate_answers": {
                    "baseline": _snippet(content, 120),
                    "reranker_top5": _snippet(content, 180),
                    "exa_fallback_top5": _snippet(content, 200),
                },
            }
        )

    for j, r in enumerate(nlp_rows, 1):
        lang = _lang(r.get("language"))
        topic = str(r.get("topic") or "NLP topic")
        content = str(r.get("content") or "")

        query = _pick_template(NLP_TEMPLATES, lang, j).format(topic=topic)
        stem = _stem_label(topic)
        rel_ids = nlp_stems.get(stem, [int(r["id"])])
        rel_ids = _augment_relevant_ids(
            rel_ids,
            nlp_ids,
            int(r["id"]),
            target_size=max_relevant_per_query,
        )
        rel_ids = [f"nlp_doc_{x}" for x in rel_ids[:max_relevant_per_query]]
        distract = [f"nlp_doc_{x}" for x in _pick_distractors(nlp_ids, int(r["id"]), 3)]
        runs = _build_runs(rel_ids, distract, "nlp", j)

        rows.append(
            {
                "id": f"DBN{j:04d}",
                "query": query,
                "language": lang,
                "intent": "conceptual_question",
                "relevant_ids": rel_ids,
                "runs": runs,
                "reference_answer": _snippet(content, 260),
                "candidate_answers": {
                    "baseline": _snippet(content, 120),
                    "reranker_top5": _snippet(content, 180),
                    "exa_fallback_top5": _snippet(content, 200),
                },
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evaluation dataset from PostgreSQL")
    parser.add_argument("--output", default="evaluation/test_dataset_db.json")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL") or DEFAULT_DB_URL)
    parser.add_argument("--legal-limit", type=int, default=60)
    parser.add_argument("--nlp-limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-relevant-per-query", type=int, default=4)
    args = parser.parse_args()

    count = asyncio.run(
        build_dataset(
            output_path=Path(args.output),
            db_url=args.db_url,
            legal_limit=args.legal_limit,
            nlp_limit=args.nlp_limit,
            seed=args.seed,
            max_relevant_per_query=args.max_relevant_per_query,
        )
    )
    print(f"Generated {count} rows at {args.output}")


if __name__ == "__main__":
    main()
