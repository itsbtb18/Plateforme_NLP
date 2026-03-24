"""
LLM-powered validation layer for scraped items.

Uses the Groq API (separate key from the chatbot) to:
  • Check relevance to Arabic / NLP domain
  • Detect content language
  • Fill missing fields
  • Normalize dates to ISO-8601
  • Translate title / description to Arabic when absent
  • Score quality 0–100
  • Detect spam or promotional content

Design principles:
  - Never blocks the scraping pipeline — returns the original data on any failure.
  - Retries on malformed JSON (configurable).
  - Per-call timeout so a slow LLM doesn't stall the worker.
  - Stateless — each call is independent.
"""

import json
import logging
import re
import time
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# Expected keys in the LLM response — used for basic schema validation.
EXPECTED_KEYS = {
    "is_relevant",
    "relevance_reason",
    "detected_language",
    "quality_score",
    "is_spam",
    "spam_reason",
    "title_en",
    "title_ar",
    "description_en",
    "description_ar",
    "normalized_dates",
    "filled_fields",
}


# ─── Prompt templates ──────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert Arabic-NLP data-quality assistant.
You receive a scraped item (JSON) from the web and must validate, enrich,
and translate it.  Always reply with a SINGLE JSON object — no markdown
fences, no commentary.

### Your tasks
1. **Relevance**: Is this item relevant to Natural Language Processing, \
Computational Linguistics, or Arabic language technology?  \
Set `is_relevant` (bool) and `relevance_reason` (1 sentence).
2. **Language detection**: `detected_language` — ISO-639-1 code of the \
*dominant* language of the input content (e.g. "en", "ar", "fr").
3. **Quality score**: `quality_score` — integer 0-100.  \
100 = perfect academic content; 0 = garbage / spam.
4. **Spam detection**: `is_spam` (bool), `spam_reason` (string, empty if not spam).
5. **English title & description**: `title_en`, `description_en` — \
clean, well-formed English text.  Fix typos, remove ads, normalise casing.
6. **Arabic translation**: `title_ar`, `description_ar` — faithful \
Arabic translations.  If Arabic text already exists, improve it if needed.
7. **Date normalisation**: `normalized_dates` — an object whose keys are \
the original date field names and values are ISO-8601 strings (YYYY-MM-DD) \
or null if unparseable.
8. **Fill missing fields**: `filled_fields` — an object with any \
field names you can infer or correct (e.g. email, location, event_type). \
Only include fields you are confident about.

### Output schema (strict)
```json
{
  "is_relevant": true,
  "relevance_reason": "...",
  "detected_language": "en",
  "quality_score": 85,
  "is_spam": false,
  "spam_reason": "",
  "title_en": "...",
  "title_ar": "...",
  "description_en": "...",
  "description_ar": "...",
  "normalized_dates": {"start_date": "2025-07-27", "end_date": "2025-08-01"},
  "filled_fields": {"contact_email": "info@example.org"}
}
```
Return ONLY the JSON object.  No extra text.\
"""

USER_PROMPT_TEMPLATE = """\
Category: {category}

Scraped item:
```json
{item_json}
```

Validate, enrich, translate, and return the strict JSON schema.\
"""


CUSTOM_EXTRACTION_INSTRUCTIONS = {
    "events": (
        "Extract event entries from this page. Include title, description, url, date, "
        "location, event_type (conference/workshop/seminar/cfp), and organizer if visible."
    ),
    "tools": (
        "Extract from this page: tool name, what it does, programming language, "
        "github link if present, license, installation command if shown, "
        "supported languages (arabic/english/etc)."
    ),
    "news": (
        "Extract research/news entries from this page. Include title, summary, url, "
        "publication date, and source name if visible."
    ),
    "courses": (
        "Extract: course title, instructor name, institution, course level "
        "(beginner/intermediate/advanced), language of instruction, duration, "
        "whether it is free, platform name."
    ),
    "institutions": (
        "Extract: institution full name, acronym, type (university/research lab/center), "
        "country, city, website, main research areas, director name if shown."
    ),
}


def build_custom_extraction_prompt(category: str, page_text: str) -> tuple[str, str]:
    """Build category-specific prompts for flexible custom-source extraction."""
    normalized_category = (category or "").strip().lower()
    instruction = CUSTOM_EXTRACTION_INSTRUCTIONS.get(
        normalized_category,
        CUSTOM_EXTRACTION_INSTRUCTIONS["news"],
    )

    system_prompt = (
        "You are a strict extraction assistant for Arabic NLP curation. "
        "Return only a valid JSON array. No markdown. No explanation."
    )
    user_prompt = f"""
Category: {normalized_category or "auto"}

Task:
{instruction}

Output format:
- Return ONLY a JSON array.
- Each object may include any relevant fields, but always include:
  - title or name
  - description (or summary)
  - url (if available)
  - date (if available, ISO YYYY-MM-DD preferred)
- If no items are present, return [].
- Do not invent facts.

Webpage text:
{page_text}
"""
    return system_prompt, user_prompt


# ─── GroqLLMClient ─────────────────────────────────────────────────


class GroqLLMClient:
    """Thin wrapper around the Groq Chat Completions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings, "GROQ_SCRAPING_API_KEY", "")
        self.model = model or getattr(
            settings, "GROQ_SCRAPING_MODEL", "llama-3.3-70b-versatile"
        )
        configured_timeout = timeout or getattr(settings, "GROQ_SCRAPING_TIMEOUT", 30)
        self.timeout = max(1, min(int(configured_timeout), 30))
        self.max_retries = max_retries or getattr(
            settings, "GROQ_SCRAPING_MAX_RETRIES", 2
        )
        self._session = requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ── Core chat call ──────────────────────────────────────────────
    def _chat(self, system: str, user: str) -> Optional[str]:
        """Send a chat completion request and return the assistant text."""
        if not self.is_configured:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.15,
            "max_tokens": 2048,
        }
        try:
            resp = self._session.post(
                GROQ_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.Timeout:
            logger.warning("Groq API timeout after %ds", self.timeout)
        except requests.RequestException as exc:
            logger.warning("Groq API request failed: %s", exc)
        except (KeyError, IndexError):
            logger.warning("Unexpected Groq response structure")
        return None


# ─── JSON parsing helpers ──────────────────────────────────────────


def _extract_json(text: str) -> Optional[dict]:
    """Try to extract a JSON object from LLM output (may contain fences)."""
    if not text:
        return None
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fallback: find the first { … } block
    match = re.search(r"\{[\s\S]+\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _validate_schema(obj: dict) -> bool:
    """Return True if the response has the minimum required keys."""
    return EXPECTED_KEYS.issubset(obj.keys())


# ─── Public API ────────────────────────────────────────────────────


class LLMValidator:
    """
    Validate a single scraped item through the Groq LLM.

    Usage::

        validator = LLMValidator()
        enriched = validator.validate(item_dict, category="events")
        if enriched and enriched["is_relevant"] and not enriched["is_spam"]:
            # apply enriched fields before saving …

    If the LLM is unavailable or returns bad data, ``validate()`` returns
    ``None`` so the caller can proceed with the original item unchanged.
    """

    def __init__(self, client: Optional[GroqLLMClient] = None):
        self.client = client or GroqLLMClient()

    @property
    def is_available(self) -> bool:
        return self.client.is_configured

    def validate(
        self, item: dict[str, Any], category: str = "general"
    ) -> Optional[dict[str, Any]]:
        """
        Send *item* to the LLM for validation and enrichment.

        Returns the parsed JSON dict on success, or ``None`` on any failure
        (timeout, bad JSON, missing keys, network error).
        """
        if not self.is_available:
            logger.debug("LLM validation skipped — no API key configured")
            return None

        user_prompt = USER_PROMPT_TEMPLATE.format(
            category=category,
            item_json=json.dumps(item, ensure_ascii=False, default=str),
        )

        for attempt in range(1, self.client.max_retries + 1):
            raw = self.client._chat(SYSTEM_PROMPT, user_prompt)
            if raw is None:
                # Network / timeout failure — don't retry
                return None

            parsed = _extract_json(raw)
            if parsed is not None and _validate_schema(parsed):
                return parsed

            logger.debug(
                "LLM JSON parse attempt %d/%d failed (category=%s)",
                attempt,
                self.client.max_retries,
                category,
            )
            # Brief pause before retry
            time.sleep(0.3)

        logger.warning(
            "LLM validation gave up after %d retries for category=%s",
            self.client.max_retries,
            category,
        )
        return None


# ─── Convenience helpers for scrapers ──────────────────────────────

# Module-level singleton — lazily created on first use.
_default_validator: Optional[LLMValidator] = None


def get_validator() -> LLMValidator:
    """Return the module-level LLMValidator singleton."""
    global _default_validator
    if _default_validator is None:
        _default_validator = LLMValidator()
    return _default_validator


def validate_item(item: dict, category: str = "general") -> Optional[dict]:
    """
    Shortcut: validate a single item using the default validator.

    Returns the enriched dict or ``None`` on failure.
    """
    return get_validator().validate(item, category)


def apply_llm_enrichment(
    original: dict[str, Any],
    enriched: dict[str, Any],
    *,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """
    Merge LLM-enriched fields back into the original item dict.

    By default only *missing* fields are filled.  Set
    ``overwrite_existing=True`` to always prefer the LLM version.

    Returns a **new** dict (does not mutate *original*).
    """
    merged = dict(original)

    # Direct field mappings
    for key in ("title_en", "title_ar", "description_en", "description_ar"):
        val = enriched.get(key)
        if val and (overwrite_existing or not merged.get(key)):
            merged[key] = val

    # Normalized dates
    for date_key, iso_val in (enriched.get("normalized_dates") or {}).items():
        if iso_val and (overwrite_existing or not merged.get(date_key)):
            merged[date_key] = iso_val

    # Filled fields (LLM-inferred extras)
    for fkey, fval in (enriched.get("filled_fields") or {}).items():
        if fval and (overwrite_existing or not merged.get(fkey)):
            merged[fkey] = fval

    return merged


# ─── Academic Paper Enrichment ─────────────────────────────────────

PAPER_SYSTEM_PROMPT = """\
You are an expert academic research assistant specialising in Natural \
Language Processing and Arabic language technology.

You receive the title, abstract, and optionally the first pages of a \
research paper.  Your task is to produce a structured enrichment.

### Tasks
1. **Short summary** (`summary_short`): 2-3 sentence plain-English summary.
2. **Long summary** (`summary_long`): 1 paragraph (4-8 sentences) with \
key contributions, methods, and findings.
3. **Arabic summary** (`summary_ar`): Faithful Arabic translation of the \
short summary.
4. **Keywords** (`keywords`): list of 5-10 lowercase keywords/phrases.
5. **Research domain** (`research_domain`): One of: \
"nlp", "machine_translation", "sentiment_analysis", "ner", \
"speech_processing", "information_retrieval", "text_mining", \
"question_answering", "text_generation", "summarization", \
"computational_linguistics", "arabic_nlp", "multimodal", "other".
6. **Sub-domains** (`sub_domains`): list of 1-3 more-specific labels \
(free text, e.g. "dialectal Arabic", "transformer fine-tuning").
7. **Relevance to Arabic NLP** (`arabic_nlp_relevance`): float 0.0-1.0.

### Output schema (strict)
```json
{
  "summary_short": "...",
  "summary_long": "...",
  "summary_ar": "...",
  "keywords": ["keyword1", "keyword2"],
  "research_domain": "nlp",
  "sub_domains": ["sub1", "sub2"],
  "arabic_nlp_relevance": 0.85
}
```
Return ONLY the JSON object.  No markdown fences, no commentary.\
"""

PAPER_USER_TEMPLATE = """\
Title: {title}

Authors: {authors}

Abstract:
{abstract}

{pdf_section}\
Produce the enrichment JSON.\
"""

PAPER_EXPECTED_KEYS = {
    "summary_short",
    "summary_long",
    "summary_ar",
    "keywords",
    "research_domain",
    "sub_domains",
    "arabic_nlp_relevance",
}


def enrich_paper(
    title: str,
    abstract: str,
    *,
    authors: str = "",
    pdf_text: str | None = None,
) -> dict[str, Any] | None:
    """
    Send a paper's metadata (and optional PDF text) to the LLM for
    structured enrichment.

    Returns a dict with summary_short, summary_long, summary_ar, keywords,
    research_domain, sub_domains, arabic_nlp_relevance — or ``None`` on
    any failure.
    """
    validator = get_validator()
    if not validator.is_available:
        logger.debug("Paper enrichment skipped — no API key configured")
        return None

    pdf_section = ""
    if pdf_text:
        # Truncate PDF text to avoid exceeding token limits
        truncated = pdf_text[:8000]
        pdf_section = f"Extracted PDF text (first pages):\n{truncated}\n\n"

    user_prompt = PAPER_USER_TEMPLATE.format(
        title=title,
        authors=authors,
        abstract=abstract or "(no abstract available)",
        pdf_section=pdf_section,
    )

    client = validator.client
    for attempt in range(1, client.max_retries + 1):
        raw = client._chat(PAPER_SYSTEM_PROMPT, user_prompt)
        if raw is None:
            return None

        parsed = _extract_json(raw)
        if parsed is not None and PAPER_EXPECTED_KEYS.issubset(parsed.keys()):
            # Normalise types
            if isinstance(parsed.get("keywords"), str):
                parsed["keywords"] = [k.strip() for k in parsed["keywords"].split(",")]
            if isinstance(parsed.get("sub_domains"), str):
                parsed["sub_domains"] = [parsed["sub_domains"]]
            return parsed

        logger.debug(
            "Paper enrichment JSON attempt %d/%d failed",
            attempt,
            client.max_retries,
        )
        time.sleep(0.3)

    logger.warning("Paper enrichment gave up after %d retries", client.max_retries)
    return None


def build_enriched_content(
    *,
    authors: str,
    abstract: str,
    source_url: str,
    pdf_url: str = "",
    published: str = "",
    year: str = "",
    categories: str = "",
    enrichment: dict[str, Any] | None = None,
) -> str:
    """
    Build the rich Markdown content for a ``QA.Post`` from paper metadata
    and optional LLM enrichment.  Falls back gracefully when *enrichment*
    is ``None``.
    """
    parts: list[str] = []

    if authors:
        parts.append(f"**Authors:** {authors}")

    if year:
        parts.append(f"**Year:** {year}")

    # LLM-enriched sections
    if enrichment:
        if enrichment.get("summary_short"):
            parts.append(f"**Summary:** {enrichment['summary_short']}")
        if enrichment.get("summary_long"):
            parts.append(f"**Detailed Summary:** {enrichment['summary_long']}")
        if enrichment.get("keywords"):
            kw = ", ".join(enrichment["keywords"])
            parts.append(f"**Keywords:** {kw}")
        if enrichment.get("research_domain"):
            domain = enrichment["research_domain"].replace("_", " ").title()
            parts.append(f"**Research Domain:** {domain}")
        if enrichment.get("sub_domains"):
            parts.append(f"**Sub-domains:** {', '.join(enrichment['sub_domains'])}")

    # Always include the original abstract
    if abstract:
        parts.append(f"**Abstract:** {abstract}")

    if categories:
        parts.append(f"**Categories:** {categories}")

    # Links
    links = []
    if source_url:
        links.append(f"[Read the full paper]({source_url})")
    if pdf_url:
        links.append(f"[PDF]({pdf_url})")
    if links:
        parts.append(" | ".join(links))

    return "\n\n".join(parts)


def build_enriched_content_ar(
    enrichment: dict[str, Any] | None,
    *,
    fallback: str = "",
) -> str:
    """Build Arabic content from enrichment, or return *fallback*."""
    if not enrichment:
        return fallback
    return enrichment.get("summary_ar") or fallback
