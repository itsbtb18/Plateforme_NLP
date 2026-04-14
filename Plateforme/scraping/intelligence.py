"""
Scraping Intelligence Module — Phase 6
=======================================

Provides:
1. **Keyword Expansion** — Arabic NLP ontology with EN/AR terms
2. **Auto Query Generation** — dynamic query combiner for APIs
3. **Domain Classification** — rule-based + lightweight LLM fallback
4. **Scoring / Ranking** — relevance scoring for scraped items
5. **Trend Detection** — analyse last 6 months of scraping data
"""

import datetime
import logging
import re
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from scraping.utils import apply_translation_confidence_cap

logger = logging.getLogger(__name__)


# =====================================================================
# 1. KEYWORD ONTOLOGY — Arabic NLP domain terms
# =====================================================================

# Each domain has English terms, Arabic terms, and related sub-fields.
DOMAIN_ONTOLOGY = {
    "arabic_nlp": {
        "label_en": "Arabic NLP",
        "label_ar": "معالجة اللغة العربية الطبيعية",
        "keywords_en": [
            "arabic nlp",
            "arabic natural language processing",
            "arabic text processing",
            "arabic language technology",
            "arabic text mining",
            "arabic information extraction",
            "arabic morphological analysis",
            "arabic tokenization",
            "arabic stemming",
            "arabic lemmatization",
            "arabic pos tagging",
            "arabic named entity recognition",
            "arabic ner",
            "arabic word segmentation",
            "arabic diacritization",
            "arabic tashkeel",
            "arabic spell checking",
            "arabic ocr",
            "arabic text classification",
            "arabic sentiment analysis",
            "arabic question answering",
            "arabic summarization",
            "arabic machine translation",
            "arabic mt",
            "arabic word embeddings",
            "arabic bert",
            "arabert",
            "camelbert",
            "arabic language model",
            "dialectal arabic",
            "arabic dialect processing",
            "maghrebi arabic",
            "algerian arabic",
            "darija",
            "levantine arabic",
            "gulf arabic",
            "egyptian arabic",
            "modern standard arabic",
            "msa",
        ],
        "keywords_ar": [
            "المعالجة اللغوية الطبيعية العربية",
            "معالجة النصوص العربية",
            "تقنية اللغة العربية",
            "التنقيب في النصوص العربية",
            "التحليل الصرفي العربي",
            "الترميز العربي",
            "التجذير العربي",
            "تصنيف النصوص العربية",
            "تحليل المشاعر العربية",
            "الترجمة الآلية العربية",
            "التعرف على الكيانات المسماة",
            "التشكيل التلقائي",
            "اللهجات العربية",
            "اللهجة الجزائرية",
            "الدارجة المغاربية",
        ],
    },
    "arabic_languages": {
        "label_en": "Arabic Languages & Linguistics",
        "label_ar": "اللغويات العربية",
        "keywords_en": [
            "arabic linguistics",
            "arabic language",
            "arabic corpus",
            "arabic corpora",
            "arabic grammar",
            "arabic syntax",
            "arabic phonology",
            "arabic morphology",
            "arabic semantics",
            "arabic pragmatics",
            "arabic lexicon",
            "arabic dictionary",
            "arabic script",
            "arabic writing system",
            "classical arabic",
            "quranic arabic",
            "arabic dialectology",
            "arabic sociolinguistics",
            "amazigh language",
            "tamazight",
            "berber language",
            "kabyle",
            "tuareg language",
            "arabic calligraphy",
            "arabic typography",
            "arabic unicode",
            "arabic text rendering",
            "arabic language resources",
            "arabic treebank",
            "arabic wordnet",
            "arabic ontology",
        ],
        "keywords_ar": [
            "اللغويات العربية",
            "علم اللغة العربية",
            "المدونة اللغوية العربية",
            "النحو العربي",
            "الصرف العربي",
            "علم الأصوات العربية",
            "المعجم العربي",
            "العربية الفصحى",
            "العربية الكلاسيكية",
            "اللغة الأمازيغية",
            "تمازيغت",
            "اللغة القبائلية",
        ],
    },
    "speech_processing": {
        "label_en": "Speech Processing",
        "label_ar": "معالجة الكلام",
        "keywords_en": [
            "speech processing",
            "speech recognition",
            "automatic speech recognition",
            "asr",
            "text to speech",
            "tts",
            "speech synthesis",
            "arabic speech",
            "arabic asr",
            "arabic tts",
            "arabic voice",
            "arabic speaker recognition",
            "arabic speech dataset",
            "arabic audio",
            "whisper arabic",
            "wav2vec arabic",
            "massively multilingual speech",
            "mms",
            "spoken language understanding",
            "voice assistant arabic",
            "speech translation",
            "arabic dialogue systems",
            "conversational ai arabic",
            "arabic speech corpus",
        ],
        "keywords_ar": [
            "معالجة الكلام",
            "التعرف على الكلام",
            "التعرف التلقائي على الكلام",
            "تحويل النص إلى كلام",
            "تركيب الكلام",
            "الكلام العربي",
            "التعرف على المتحدث",
            "الحوار العربي",
        ],
    },
    "llm_research": {
        "label_en": "LLM Research",
        "label_ar": "أبحاث النماذج اللغوية الكبيرة",
        "keywords_en": [
            "large language model",
            "llm",
            "arabic llm",
            "arabic language model",
            "jais",
            "acegpt",
            "allam",
            "instruction tuning arabic",
            "rlhf arabic",
            "arabic chatbot",
            "arabic conversational ai",
            "arabic text generation",
            "arabic gpt",
            "fine-tuning arabic",
            "arabic prompt engineering",
            "multilingual llm",
            "cross-lingual transfer",
            "transformer",
            "attention mechanism",
            "pre-training",
            "foundation model",
            "retrieval augmented generation",
            "rag",
            "arabic knowledge base",
            "arabic qa",
            "arabic reasoning",
            "arabic benchmarks",
            "arabic evaluation",
            "alghafa",
            "arabic glue",
        ],
        "keywords_ar": [
            "النماذج اللغوية الكبيرة",
            "نموذج لغوي كبير",
            "الذكاء الاصطناعي التوليدي",
            "توليد النصوص العربية",
            "جيس",
            "الضبط الدقيق",
            "التعلم المعزز",
            "المحادثة العربية",
        ],
    },
}

# Flat lookup: keyword (lower) → set of domain keys
_KEYWORD_TO_DOMAINS: dict[str, set[str]] = {}


def _build_keyword_index():
    """Populate _KEYWORD_TO_DOMAINS from the ontology (called once)."""
    if _KEYWORD_TO_DOMAINS:
        return
    for domain_key, info in DOMAIN_ONTOLOGY.items():
        for kw in info["keywords_en"]:
            _KEYWORD_TO_DOMAINS.setdefault(kw.lower(), set()).add(domain_key)
        for kw in info["keywords_ar"]:
            _KEYWORD_TO_DOMAINS.setdefault(kw, set()).add(domain_key)


_build_keyword_index()


# =====================================================================
# 2. KEYWORD EXPANSION ENGINE
# =====================================================================


def expand_keywords(seed_terms: list[str], max_results: int = 30) -> list[str]:
    """Expand a list of seed terms using the domain ontology.

    Returns a deduplicated list of related keywords (English + Arabic)
    up to *max_results*.
    """
    expanded: list[str] = []
    seen = set()

    # First pass: include seed terms
    for term in seed_terms:
        t = term.strip()
        if t and t.lower() not in seen:
            expanded.append(t)
            seen.add(t.lower())

    # Second pass: find related domains and pull extra keywords
    matched_domains: set[str] = set()
    for term in seed_terms:
        tl = term.strip().lower()
        if tl in _KEYWORD_TO_DOMAINS:
            matched_domains.update(_KEYWORD_TO_DOMAINS[tl])

    for domain_key in matched_domains:
        info = DOMAIN_ONTOLOGY[domain_key]
        for kw in info["keywords_en"] + info["keywords_ar"]:
            k = kw if any(ord(c) > 127 for c in kw) else kw.lower()
            if k not in seen:
                expanded.append(kw)
                seen.add(k)
            if len(expanded) >= max_results:
                return expanded

    return expanded[:max_results]


# =====================================================================
# 3. AUTO QUERY GENERATION
# =====================================================================

# Base terms combined with modifiers to produce diverse API queries
_BASE_TERMS = [
    "arabic nlp",
    "arabic natural language processing",
    "arabic text processing",
    "arabic language model",
    "arabic speech recognition",
    "arabic dialect",
    "North African NLP",
]

_current_year = str(datetime.datetime.now().year)
_next_year = str(datetime.datetime.now().year + 1)

_MODIFIERS = [
    "",
    _current_year,
    _next_year,
    "deep learning",
    "transformer",
    "bert",
    "dataset",
    "benchmark",
    "low-resource",
]

_ARABIC_TERMS = [
    "المعالجة اللغوية الطبيعية",
    "معالجة النصوص العربية",
    "النماذج اللغوية الكبيرة",
    "التعرف على الكلام العربي",
]


def generate_queries(
    category: str,
    max_queries: int = 12,
    include_arabic: bool = True,
) -> list[dict]:
    """Generate dynamic search queries for a scraper category.

    Returns a list of dicts usable as API query params.
    Each dict has at minimum a ``"search"`` or ``"query"`` key.
    """
    queries: list[dict] = []
    seen = set()

    # Combine base terms with modifiers
    for base in _BASE_TERMS:
        for mod in _MODIFIERS:
            q = f"{base} {mod}".strip()
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            queries.append({"search": q, "limit": 10})
            if len(queries) >= max_queries:
                break
        if len(queries) >= max_queries:
            break

    # Add Arabic queries if requested
    if include_arabic and len(queries) < max_queries:
        for ar_term in _ARABIC_TERMS:
            if len(queries) >= max_queries:
                break
            queries.append({"search": ar_term, "limit": 8})

    # Category-specific additions
    if category == "events":
        extras = [
            {"search": f"Arabic NLP conference {_current_year}", "limit": 10},
            {"search": "North Africa AI conference", "limit": 8},
            {"search": "MENA NLP workshop", "limit": 8},
        ]
        for e in extras:
            if len(queries) < max_queries and e["search"].lower() not in seen:
                queries.append(e)
                seen.add(e["search"].lower())

    elif category == "tools":
        extras = [
            {"search": "arabic dialect model", "limit": 8},
            {"search": "arabic speech whisper", "limit": 5},
            {"search": "arabic llm jais", "limit": 5},
            {"search": "amazigh nlp", "limit": 5},
        ]
        for e in extras:
            if len(queries) < max_queries and e["search"].lower() not in seen:
                queries.append(e)
                seen.add(e["search"].lower())

    elif category == "news":
        extras = [
            {"query": f"Arabic NLP deep learning {_current_year}", "limit": 15},
            {"query": "Maghreb AI research", "limit": 10},
            {"query": "dialectal Arabic processing", "limit": 10},
        ]
        for e in extras:
            if len(queries) < max_queries:
                queries.append(e)

    elif category == "institutions":
        extras = [
            {"search": "Arabic NLP laboratory", "limit": 10},
            {"search": "North Africa AI research center", "limit": 8},
            {"search": "MENA computer science university", "limit": 8},
        ]
        for e in extras:
            if len(queries) < max_queries and e["search"].lower() not in seen:
                queries.append(e)
                seen.add(e["search"].lower())

    return queries[:max_queries]


# =====================================================================
# 4. DOMAIN CLASSIFICATION
# =====================================================================

# Compiled regex patterns for fast rule-based classification
_DOMAIN_PATTERNS: dict[str, re.Pattern] = {}


def _build_domain_patterns():
    """Build compiled regex patterns from the ontology (called once)."""
    if _DOMAIN_PATTERNS:
        return
    for domain_key, info in DOMAIN_ONTOLOGY.items():
        # Build alternation from all keywords, escape special chars
        all_kw = info["keywords_en"] + info["keywords_ar"]
        # Sort by length descending so longer matches take priority
        all_kw.sort(key=len, reverse=True)
        pattern_str = "|".join(re.escape(kw) for kw in all_kw)
        _DOMAIN_PATTERNS[domain_key] = re.compile(pattern_str, re.IGNORECASE)


_build_domain_patterns()


def classify_domain(text: str) -> dict[str, float]:
    """Classify text into research domains using rule-based matching.

    Returns a dict of ``{domain_key: confidence_score}`` where scores
    are in [0.0, 1.0].  Only domains with score > 0 are included.
    """
    if not text:
        return {}

    results: dict[str, float] = {}

    for domain_key, pattern in _DOMAIN_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            # Score: more matches → higher confidence, capped at 1.0
            unique_matches = len(set(m.lower() for m in matches))
            # Base score from match count, logarithmic scaling
            score = min(1.0, 0.3 + 0.15 * unique_matches)
            results[domain_key] = round(score, 3)

    return results


def classify_domain_primary(text: str) -> str:
    """Return the single best-matching domain key, or 'general' if none."""
    scores = classify_domain(text)
    if not scores:
        return "general"
    return max(scores, key=scores.get)


def classify_with_llm_fallback(text: str) -> dict[str, float]:
    """Try rule-based classification; use LLM only if no match or ambiguous.

    This keeps LLM calls lightweight and cost-efficient.
    """
    scores = classify_domain(text)

    # If rule-based found clear match, use it
    if scores and max(scores.values()) >= 0.5:
        return scores

    # Lightweight LLM fallback for ambiguous or unknown items
    try:
        import json

        from scraping.extractors.core.llm_validation import GroqLLMClient

        client = GroqLLMClient()
        system = (
            "You are a research-domain classifier. "
            "Return ONLY a JSON object with domain keys and confidence scores (0.0-1.0). "
            "Valid domains: arabic_nlp, arabic_languages, speech_processing, llm_research. "
            'Example: {"arabic_nlp": 0.8, "llm_research": 0.6}'
        )
        user_msg = f"Classify this text:\n\n{text[:500]}"
        response = client._chat(system, user_msg)
        if response:
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                llm_scores = json.loads(json_match.group())
                # Validate and merge
                valid_domains = set(DOMAIN_ONTOLOGY.keys())
                for k, v in llm_scores.items():
                    if k in valid_domains and isinstance(v, (int, float)):
                        scores[k] = max(scores.get(k, 0), min(1.0, float(v)))
    except Exception as exc:
        logger.debug("LLM domain classification fallback failed: %s", exc)

    return scores or {"general": 0.3}


# =====================================================================
# 5. SCORING / RANKING SYSTEM
# =====================================================================

# Weight configuration for the scoring algorithm
SCORING_WEIGHTS = {
    "recency": 0.25,  # How recent the item is
    "relevance": 0.30,  # Domain match strength
    "source_health": 0.15,  # Source reliability
    "popularity": 0.15,  # Downloads, citations, etc.
    "completeness": 0.15,  # How much metadata is filled in
}


class ConfidenceCalculator:
    FIELD_WEIGHTS = {
        "events": {
            "title_en": 0.20,
            "title_ar": 0.15,
            "description_en": 0.15,
            "description_ar": 0.10,
            "start_date": 0.15,
            "url": 0.10,
            "location": 0.08,
            "end_date": 0.04,
            "organizer": 0.03,
        },
        "tools": {
            "title_en": 0.20,
            "title_ar": 0.15,
            "description_en": 0.20,
            "description_ar": 0.10,
            "url": 0.15,
            "capabilities": 0.10,
            "language_support": 0.10,
        },
        "courses": {
            "title_en": 0.20,
            "title_ar": 0.15,
            "description_en": 0.20,
            "description_ar": 0.10,
            "platform": 0.15,
            "url": 0.10,
            "level": 0.05,
            "price": 0.05,
        },
        "news": {
            "title_en": 0.25,
            "title_ar": 0.20,
            "description_en": 0.20,
            "description_ar": 0.15,
            "url": 0.10,
            "published_date": 0.10,
        },
        "opportunities": {
            "title_en": 0.20,
            "title_ar": 0.15,
            "description_en": 0.20,
            "description_ar": 0.10,
            "url": 0.15,
            "deadline": 0.10,
            "institution": 0.10,
        },
        "corpus": {
            "title_en": 0.20,
            "title_ar": 0.15,
            "description_en": 0.20,
            "description_ar": 0.10,
            "download_url": 0.15,
            "language_variants": 0.10,
            "size": 0.05,
            "license": 0.05,
        },
    }

    def score_field(
        self,
        field_name: str,
        value,
        en_equivalent=None,
    ) -> float:
        if value is None or value == "":
            return 0.0

        if isinstance(value, list):
            return 1.0 if value else 0.0
        if isinstance(value, dict):
            return 1.0 if value else 0.0

        value_str = str(value).strip()
        if not value_str:
            return 0.0

        if field_name.endswith("_ar"):
            return self._score_arabic_field(value_str, en_equivalent)

        if "date" in field_name or "deadline" in field_name:
            return self._score_date_field(value_str)

        if "url" in field_name:
            return self._score_url_field(value_str)

        if len(value_str) >= 3:
            return 1.0
        return 0.5

    def _score_arabic_field(self, ar_value: str, en_value: str = None) -> float:
        if not ar_value:
            return 0.0

        if en_value and ar_value.strip() == str(en_value).strip():
            return 0.1

        arabic_chars = sum(1 for c in ar_value if "\u0600" <= c <= "\u06ff")
        total_chars = len(ar_value.replace(" ", ""))

        if total_chars == 0:
            return 0.0

        arabic_ratio = arabic_chars / total_chars

        if arabic_ratio >= 0.5:
            return 1.0
        if arabic_ratio >= 0.3:
            return 0.7
        if arabic_ratio >= 0.1:
            return 0.3
        return 0.1

    def _score_date_field(self, value: str) -> float:
        import re

        date_pattern = r"\d{4}-\d{2}-\d{2}"
        if re.search(date_pattern, value):
            return 1.0
        if any(
            month in value.lower()
            for month in [
                "jan",
                "feb",
                "mar",
                "apr",
                "may",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
                "january",
                "february",
                "march",
            ]
        ):
            return 0.8
        return 0.4

    def _score_url_field(self, value: str) -> float:
        if value.startswith(("http://", "https://")):
            return 1.0
        if "." in value:
            return 0.6
        return 0.2

    def calculate(self, category: str, item_data: dict) -> dict:
        weights = self.FIELD_WEIGHTS.get(category, {})
        if not weights:
            return {"score": 0.5, "percent": 50.0, "breakdown": {}, "grade": "C"}

        total_weight = sum(weights.values())
        weighted_score = 0.0
        breakdown = {}

        for field, weight in weights.items():
            value = item_data.get(field)
            en_field = field.replace("_ar", "_en")
            en_value = item_data.get(en_field) if "_ar" in field else None

            field_score = self.score_field(field, value, en_value)
            weighted_score += field_score * weight
            breakdown[field] = {
                "score": round(field_score, 2),
                "weight": weight,
                "value_present": value is not None and value != "",
            }

        final_score = weighted_score / total_weight if total_weight > 0 else 0

        return {
            "score": round(final_score, 3),
            "percent": round(final_score * 100, 1),
            "breakdown": breakdown,
            "grade": (
                "A"
                if final_score >= 0.9
                else "B"
                if final_score >= 0.8
                else "C"
                if final_score >= 0.7
                else "D"
                if final_score >= 0.6
                else "F"
            ),
        }


_CONFIDENCE_CALCULATOR = ConfidenceCalculator()


def calculate_item_confidence(category: str, item_data: dict) -> dict:
    """Return weighted extraction confidence report for one category item."""
    return _CONFIDENCE_CALCULATOR.calculate(category, item_data or {})


def _safe_days_ago(date_value):
    """
    Safely compute days between a date/datetime
    and now. Handles naive/aware datetime mixing.
    Returns None if computation fails.
    """
    if date_value is None:
        return None
    try:
        import datetime

        from django.utils import timezone

        if isinstance(date_value, str):
            from dateutil import parser as date_parser

            date_value = date_parser.parse(date_value)

        now = timezone.now()

        # Handle datetime.date (not datetime)
        if isinstance(date_value, datetime.date) and not isinstance(
            date_value, datetime.datetime
        ):
            date_value = datetime.datetime.combine(
                date_value, datetime.time.min, tzinfo=datetime.UTC
            )

        # Handle naive datetime
        if isinstance(date_value, datetime.datetime) and date_value.tzinfo is None:
            import pytz

            date_value = pytz.utc.localize(date_value)

        delta = now - date_value
        return delta.days

    except Exception:
        return None


def compute_relevance_score(
    *,
    category: str | None = None,
    item_data: dict | None = None,
    text: str = "",
    created_date=None,
    source_health_score: float = 100.0,
    downloads: int = 0,
    citations: int = 0,
    likes: int = 0,
    has_description: bool = True,
    has_website: bool = True,
    has_arabic: bool = False,
    domain_scores: dict[str, float] | None = None,
    translation_status: str = "pending",
) -> float:
    """Compute a 0-100 relevance score for a scraped item.

    Parameters
    ----------
    text : str
        Combined title + description for domain matching.
    created_date : date | datetime | None
        When the item was created/published.
    source_health_score : float
        Health score of the scraping source (0-100).
    downloads, citations, likes : int
        Popularity metrics.
    has_description, has_website, has_arabic : bool
        Completeness flags.
    domain_scores : dict | None
        Pre-computed domain classification scores (if available).

    Returns
    -------
    float
        Score in range [0, 100].
    """
    if category and isinstance(item_data, dict):
        report = calculate_item_confidence(category, item_data)
        score = float(report.get("percent", 0.0))
        capped_score = apply_translation_confidence_cap(score, translation_status)
        return float(capped_score if capped_score is not None else score)

    # ── Recency score (0-1) ──
    recency = 0.7  # default for unknown date
    if created_date:
        days_old = _safe_days_ago(created_date)
        if days_old is None:
            recency = 0.5
        elif days_old <= 30:
            recency = 1.0
        elif days_old <= 90:
            recency = 0.85
        elif days_old <= 180:
            recency = 0.7
        elif days_old <= 365:
            recency = 0.5
        else:
            recency = max(0.1, 0.5 - (days_old - 365) / 3650)

    # ── Relevance score (0-1) ──
    if domain_scores is None:
        domain_scores = classify_domain(text) if text else {}
    relevance = max(domain_scores.values()) if domain_scores else 0.35

    # ── Source health (0-1) ──
    health = source_health_score / 100.0

    # ── Popularity (0-1) — log-scaled ──
    import math

    pop_raw = downloads + citations * 10 + likes * 5
    popularity = min(1.0, math.log1p(pop_raw) / 15.0) if pop_raw > 0 else 0.2

    # ── Completeness (0-1) ──
    completeness_flags = [has_description, has_website, has_arabic, bool(text)]
    completeness = sum(completeness_flags) / len(completeness_flags)

    # ── Weighted final score ──
    raw = (
        SCORING_WEIGHTS["recency"] * recency
        + SCORING_WEIGHTS["relevance"] * relevance
        + SCORING_WEIGHTS["source_health"] * health
        + SCORING_WEIGHTS["popularity"] * popularity
        + SCORING_WEIGHTS["completeness"] * completeness
    )
    score = round(raw * 100, 1)
    capped_score = apply_translation_confidence_cap(score, translation_status)
    return float(capped_score if capped_score is not None else score)


# =====================================================================
# 6. TREND DETECTION
# =====================================================================


def detect_trends(months: int = 6) -> dict:
    """Analyse scraping data from the last N months to identify trends.

    Returns a dict with:
      - ``top_domains``: most active research domains
      - ``growing_topics``: topics with increasing item counts
      - ``top_sources``: most productive scraping sources
      - ``category_counts``: items per category
      - ``monthly_activity``: items created per month
    """
    from scraping.models import ScrapingRun, ScrapingSourceHealth

    cutoff = timezone.now() - timedelta(days=months * 30)

    # ── Category counts from recent runs ──
    ScrapingRun.objects.filter(
        started_at__gte=cutoff,
        status="completed",
    ).values("category")

    category_counts: dict[str, int] = {}
    category_items: dict[str, int] = {}
    for run in ScrapingRun.objects.filter(started_at__gte=cutoff, status="completed"):
        cat = run.category
        category_counts[cat] = category_counts.get(cat, 0) + 1
        category_items[cat] = category_items.get(cat, 0) + run.items_created

    # ── Monthly activity ──
    monthly: dict[str, int] = {}
    for run in ScrapingRun.objects.filter(started_at__gte=cutoff, status="completed"):
        month_key = run.started_at.strftime("%Y-%m")
        monthly[month_key] = monthly.get(month_key, 0) + run.items_created

    # ── Top sources by health ──
    top_sources = list(
        ScrapingSourceHealth.objects.filter(
            total_successes__gt=0,
        )
        .order_by("-health_score", "-total_successes")
        .values("source_name", "category", "health_score", "total_successes")[:10]
    )

    # ── Domain trends via recent items ──
    domain_counter: Counter = Counter()
    try:
        _analyse_recent_items(cutoff, domain_counter)
    except Exception as exc:
        logger.warning(
            "trend_domain_analysis_failed",
            extra={"error": str(exc), "context": f"start={cutoff}"},
            exc_info=False,
        )

    top_domains = domain_counter.most_common(8)

    # ── Growing topics (compare first half vs second half of period) ──
    midpoint = cutoff + timedelta(days=(months * 30) // 2)
    first_half: Counter = Counter()
    second_half: Counter = Counter()
    try:
        _analyse_recent_items(cutoff, first_half, end_date=midpoint)
        _analyse_recent_items(midpoint, second_half)
    except Exception as exc:
        logger.warning(
            "trend_growth_analysis_failed",
            extra={
                "error": str(exc),
                "context": f"start={cutoff}, midpoint={midpoint}",
            },
            exc_info=False,
        )

    growing = []
    for topic, count_2 in second_half.items():
        count_1 = first_half.get(topic, 0)
        if count_2 > count_1:
            growth = (count_2 - count_1) / max(count_1, 1) * 100
            growing.append(
                {"topic": topic, "growth_pct": round(growth, 1), "count": count_2}
            )
    growing.sort(key=lambda x: x["growth_pct"], reverse=True)

    return {
        "period_months": months,
        "category_counts": category_items,
        "run_counts": category_counts,
        "monthly_activity": dict(sorted(monthly.items())),
        "top_sources": top_sources,
        "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
        "growing_topics": growing[:10],
    }


def _analyse_recent_items(cutoff, counter: Counter, end_date=None):
    """Count domain occurrences across recent scraped items."""
    date_filter_start = {"created_at__gte": cutoff} if hasattr(cutoff, "date") else {}
    date_filter_end = {"created_at__lt": end_date} if end_date else {}

    # Check events
    try:
        from events.models import Event

        qs = Event.objects.filter(**date_filter_start, **date_filter_end)
        for ev in qs.values_list("title_en", "description_en"):
            text = f"{ev[0]} {ev[1]}"
            for domain in classify_domain(text):
                counter[domain] += 1
    except Exception as exc:
        logger.warning(
            "trend_events_analysis_failed",
            extra={
                "error": str(exc),
                "context": f"start={cutoff}, end={end_date}",
            },
            exc_info=False,
        )

    # Check news posts
    try:
        from feed.models import Post

        qs = Post.objects.filter(**date_filter_start, **date_filter_end)
        for post in qs.values_list("title_en", "content_en"):
            text = f"{post[0]} {(post[1] or '')[:300]}"
            for domain in classify_domain(text):
                counter[domain] += 1
    except Exception as exc:
        logger.warning(
            "trend_news_analysis_failed",
            extra={
                "error": str(exc),
                "context": f"start={cutoff}, end={end_date}",
            },
            exc_info=False,
        )

    # Check tools
    try:
        from resources.models import NLPTool

        qs = NLPTool.objects.filter(**date_filter_start, **date_filter_end)
        for tool in qs.values_list("title_en", "description_en"):
            text = f"{tool[0]} {tool[1]}"
            for domain in classify_domain(text):
                counter[domain] += 1
    except Exception as exc:
        logger.warning(
            "trend_tools_analysis_failed",
            extra={
                "error": str(exc),
                "context": f"start={cutoff}, end={end_date}",
            },
            exc_info=False,
        )
