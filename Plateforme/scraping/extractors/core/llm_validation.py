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
from typing import Any
from urllib.parse import quote_plus

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_CHAT_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)

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
    """Scraping LLM client with provider routing (Gemini/Groq)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
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

        self.primary_provider = str(
            getattr(settings, "SCRAPING_LLM_PRIMARY_PROVIDER", "gemini")
        ).strip().lower()
        self.fallback_provider = str(
            getattr(settings, "SCRAPING_LLM_FALLBACK_PROVIDER", "groq")
        ).strip().lower()
        self.mode = str(
            getattr(settings, "SCRAPING_LLM_MODE", "primary_with_fallback")
        ).strip().lower()

        self.gemini_api_key = str(
            getattr(settings, "GEMINI_SCRAPING_API_KEY", "") or ""
        ).strip()
        self.gemini_model = str(
            getattr(settings, "GEMINI_SCRAPING_MODEL", "gemini-2.5-flash")
            or "gemini-2.5-flash"
        ).strip()
        self.gemini_timeout = max(
            1,
            min(int(getattr(settings, "GEMINI_SCRAPING_TIMEOUT", 30) or 30), 60),
        )
        self.gemini_max_retries = max(
            0,
            int(getattr(settings, "GEMINI_SCRAPING_MAX_RETRIES", 2) or 2),
        )
        self.gemini_max_rpm = max(
            1,
            int(getattr(settings, "GEMINI_SCRAPING_MAX_RPM", 10) or 10),
        )

        self._session = requests.Session()
        self._gemini_request_timestamps: list[float] = []
        self.last_status_code: int | None = None
        self.last_error_message: str = ""
        self.last_provider_used: str = ""

    @property
    def is_configured(self) -> bool:
        return self._is_provider_configured(self.primary_provider) or self._is_provider_configured(
            self.fallback_provider
        )

    def _is_provider_configured(self, provider: str) -> bool:
        normalized = (provider or "").strip().lower()
        if normalized == "gemini":
            return bool(self.gemini_api_key)
        if normalized == "groq":
            return bool(self.api_key)
        return False

    @staticmethod
    def _is_retryable_status(status_code: int | None) -> bool:
        if not isinstance(status_code, int):
            return True
        return status_code in {408, 409, 413, 429, 500, 502, 503, 504}

    def _respect_gemini_rate_limit(self) -> None:
        now = time.time()
        window_start = now - 60.0
        self._gemini_request_timestamps = [
            ts for ts in self._gemini_request_timestamps if ts >= window_start
        ]

        if len(self._gemini_request_timestamps) >= self.gemini_max_rpm:
            oldest = self._gemini_request_timestamps[0]
            sleep_for = max(0.0, 60.0 - (now - oldest))
            if sleep_for > 0:
                logger.info("Gemini free-tier rate limiting sleep=%.2fs", sleep_for)
                time.sleep(sleep_for)

        self._gemini_request_timestamps.append(time.time())

    def _chat_with_groq(self, system: str, user: str) -> str | None:
        if not self.api_key:
            self.last_error_message = "groq_not_configured"
            self.last_status_code = None
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
            "max_tokens": 1200,
        }
        try:
            resp = self._session.post(
                GROQ_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            self.last_status_code = int(resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            self.last_provider_used = "groq"
            return data["choices"][0]["message"]["content"]
        except requests.Timeout:
            self.last_error_message = "timeout"
            self.last_status_code = 408
            logger.info("Groq API timeout after %ds", self.timeout)
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int):
                self.last_status_code = status_code
            self.last_error_message = str(exc)
            if status_code in {413, 429}:
                logger.info(
                    "Groq API constrained request status=%s: %s",
                    status_code,
                    exc,
                )
            else:
                logger.warning("Groq API request failed: %s", exc)
        except (KeyError, IndexError):
            self.last_error_message = "Unexpected Groq response structure"
            logger.warning("Unexpected Groq response structure")
        return None

    def _chat_with_gemini(self, system: str, user: str) -> str | None:
        if not self.gemini_api_key:
            self.last_error_message = "gemini_not_configured"
            self.last_status_code = None
            return None

        self._respect_gemini_rate_limit()

        combined_prompt = (
            "System instructions:\n"
            f"{system}\n\n"
            "User request:\n"
            f"{user}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": combined_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": 1200,
            },
        }
        url = GEMINI_CHAT_URL_TEMPLATE.format(
            model=quote_plus(self.gemini_model),
            api_key=quote_plus(self.gemini_api_key),
        )

        for attempt in range(0, self.gemini_max_retries + 1):
            try:
                resp = self._session.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=self.gemini_timeout,
                )
                self.last_status_code = int(resp.status_code)
                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates") or []
                if not candidates:
                    self.last_error_message = "gemini_no_candidates"
                    return None

                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if not parts:
                    self.last_error_message = "gemini_empty_parts"
                    return None

                text = parts[0].get("text")
                if not isinstance(text, str) or not text.strip():
                    self.last_error_message = "gemini_empty_text"
                    return None

                self.last_provider_used = "gemini"
                return text
            except requests.Timeout:
                self.last_status_code = 408
                self.last_error_message = "timeout"
                logger.info("Gemini API timeout after %ds", self.gemini_timeout)
            except requests.RequestException as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if isinstance(status_code, int):
                    self.last_status_code = status_code
                self.last_error_message = str(exc)
                logger.warning("Gemini API request failed: %s", exc)
            except (KeyError, IndexError, TypeError, ValueError):
                self.last_error_message = "Unexpected Gemini response structure"
                logger.warning("Unexpected Gemini response structure")

            if attempt < self.gemini_max_retries and self._is_retryable_status(
                self.last_status_code
            ):
                time.sleep(0.5 * (attempt + 1))
                continue

            break

        return None

    def _call_provider(self, provider: str, system: str, user: str) -> str | None:
        normalized = (provider or "").strip().lower()
        if normalized == "gemini":
            return self._chat_with_gemini(system, user)
        if normalized == "groq":
            return self._chat_with_groq(system, user)
        self.last_error_message = f"unknown_provider:{normalized}"
        self.last_status_code = None
        return None

    # ── Core chat call ──────────────────────────────────────────────
    def _chat(self, system: str, user: str) -> str | None:
        """Send a chat completion request using configured routing policy."""
        if not self.is_configured:
            return None

        self.last_status_code = None
        self.last_error_message = ""

        if self.mode == "fallback_only":
            return self._call_provider(self.fallback_provider, system, user)

        primary_response = self._call_provider(self.primary_provider, system, user)
        if primary_response:
            return primary_response

        if self.mode == "primary_only":
            return None

        if self.mode != "primary_with_fallback":
            return None

        if not self._is_retryable_status(self.last_status_code):
            return None

        if self.fallback_provider == self.primary_provider:
            return None

        if not self._is_provider_configured(self.fallback_provider):
            return None

        logger.info(
            "scraping_llm_fallback from=%s to=%s status=%s",
            self.primary_provider,
            self.fallback_provider,
            self.last_status_code,
        )
        return self._call_provider(self.fallback_provider, system, user)


# ─── JSON parsing helpers ──────────────────────────────────────────


def _extract_json(text: str) -> dict | None:
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
    except json.JSONDecodeError as exc:
        logger.debug(
            "llm_json_primary_parse_fallback",
            extra={"error": str(exc), "context": cleaned[:120]},
        )

    # Fallback: find the first { … } block
    match = re.search(r"\{[\s\S]+\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.debug(
                "llm_json_regex_parse_fallback",
                extra={"error": str(exc), "context": match.group()[:120]},
            )
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

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    @property
    def is_available(self) -> bool:
        return self.client.is_configured

    def validate(
        self, item: dict[str, Any], category: str = "general"
    ) -> dict[str, Any] | None:
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

    def validate_with_fallback(
        self,
        item: dict[str, Any],
        category: str = "general",
    ) -> dict[str, Any]:
        """
        Backward-compatible validation mode.

        Returns the original payload with ``llm_validation`` status when
        enrichment cannot be produced.
        """
        payload = dict(item or {})

        if not self.is_available:
            payload.setdefault("llm_validation", "skipped")
            return payload

        enriched = self.validate(payload, category)
        if enriched is None:
            payload.setdefault("llm_validation", "no_response")
            return payload

        payload.update(enriched)
        payload["llm_validation"] = "ok"
        return payload


# ─── Convenience helpers for scrapers ──────────────────────────────

# Module-level singleton — lazily created on first use.
_default_validator: LLMValidator | None = None


def get_validator() -> LLMValidator:
    """Return the module-level LLMValidator singleton."""
    global _default_validator
    if _default_validator is None:
        _default_validator = LLMValidator()
    return _default_validator


def validate_item(item: dict, category: str = "general") -> dict | None:
    """
    Shortcut: validate a single item using the default validator.

    Returns the enriched dict or ``None`` on failure.
    """
    return get_validator().validate(item, category)


def validate_item_with_fallback(
    item: dict[str, Any],
    category: str = "general",
) -> dict[str, Any]:
    """Backward-compatible convenience wrapper around validate_with_fallback()."""
    return get_validator().validate_with_fallback(item, category)


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
