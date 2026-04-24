"""LLM-based event extraction from Tavily search results."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from typing import Any

from scraping.extractors.core.llm_validation import GroqLLMClient
from scraping.utils import infer_translation_status

logger = logging.getLogger(__name__)


class LLMEventExtractor:
    """Extract structured event payloads from Tavily search results."""

    NEEDS_RESEARCH_PLACEHOLDER = "[NEEDS RESEARCH]"

    MAX_PROMPT_RESULTS = 5
    MAX_TITLE_CHARS = 140
    MAX_URL_CHARS = 260
    MAX_CONTENT_CHARS_PER_RESULT = 340
    MAX_PROMPT_CONTENT_CHARS_TOTAL = 1400

    FALLBACK_PROMPT_RESULTS = 2
    FALLBACK_TITLE_CHARS = 70
    FALLBACK_URL_CHARS = 160
    FALLBACK_CONTENT_CHARS = 120

    EVENT_SCHEMA_KEYS = (
        "title_en",
        "title_ar",
        "description_en",
        "description_ar",
        "domain",
        "event_type",
        "start_date",
        "end_date",
        "location",
        "website",
        "registration_link",
        "attachment_url",
        "banner_image_url",
        "organizer_name",
        "tags",
        "source_url",
        "source_name",
    )

    DOMAIN_VALUES = {"nlp", "speech", "computer_vision", "ai"}
    EVENT_TYPE_VALUES = {"conference", "workshop", "seminar", "hackathon"}
    SOURCE_NAME = "Tavily Search"

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_events_from_search(
        self, search_results: list[dict]
    ) -> list[dict]:
        """Extract all upcoming Arabic NLP/AI/Speech events from search results."""
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning(
                "LLM event extraction skipped: GROQ_SCRAPING_API_KEY is not configured"
            )
            return []

        system_prompt = self._build_system_prompt()
        user_prompt = json.dumps(
            {"search_results": normalized_search_results},
            ensure_ascii=False,
            default=str,
        )

        await asyncio.to_thread(time.sleep, random.uniform(1, 3))
        try:
            response_text = await asyncio.to_thread(
                self.client._chat,
                system_prompt,
                user_prompt,
            )
        except Exception as exc:
            if self._is_rate_limited_exception(exc):
                raise RuntimeError("GROQ_RATE_LIMIT_EXCEEDED") from exc
            logger.warning("LLM event extraction call failed: %s", exc)
            return []

        if not response_text:
            if self._is_rate_limited_response():
                raise RuntimeError("GROQ_RATE_LIMIT_EXCEEDED")
            if self._is_payload_too_large_response():
                compact_results = self._compact_search_results_for_retry(
                    normalized_search_results
                )
                if not compact_results:
                    logger.warning(
                        "LLM event extraction payload too large and no compact retry payload was available"
                    )
                    return []

                compact_prompt = json.dumps(
                    {"search_results": compact_results},
                    ensure_ascii=False,
                    default=str,
                )
                logger.info(
                    "Retrying LLM event extraction with compact payload entries=%s",
                    len(compact_results),
                )
                await asyncio.to_thread(time.sleep, random.uniform(1, 3))
                try:
                    response_text = await asyncio.to_thread(
                        self.client._chat,
                        system_prompt,
                        compact_prompt,
                    )
                except Exception as exc:
                    if self._is_rate_limited_exception(exc):
                        raise RuntimeError("GROQ_RATE_LIMIT_EXCEEDED") from exc
                    logger.warning("LLM event extraction compact retry failed: %s", exc)
                    return []

                if not response_text:
                    if self._is_rate_limited_response():
                        raise RuntimeError("GROQ_RATE_LIMIT_EXCEEDED")
                    return []
            else:
                return []

        try:
            parsed = json.loads(self._strip_code_fences(response_text))
        except json.JSONDecodeError:
            cleaned = self._strip_code_fences(response_text)
            fallback_json = self._extract_json_array_block(cleaned)
            if not fallback_json:
                logger.info(
                    "LLM event extraction returned invalid JSON; using fallback extraction path"
                )
                return []
            try:
                parsed = json.loads(fallback_json)
            except json.JSONDecodeError:
                logger.info("LLM event extraction fallback JSON parsing failed")
                return []

        event_items = parsed if isinstance(parsed, list) else []
        if not event_items and isinstance(parsed, dict):
            events = parsed.get("events")
            if isinstance(events, list):
                event_items = events
            elif any(key in parsed for key in self.EVENT_SCHEMA_KEYS) or parsed.get(
                "event_url"
            ):
                event_items = [parsed]

        if not isinstance(event_items, list):
            return []

        allowed_urls = {
            entry["url"] for entry in normalized_search_results if entry.get("url")
        }

        extracted_events: list[dict] = []
        for event_item in event_items:
            if not isinstance(event_item, dict):
                continue

            normalized_event = self._normalize_event(event_item, allowed_urls)
            if normalized_event is None:
                continue
            extracted_events.append(normalized_event)

        return extracted_events

    def extract_event_candidates(
        self,
        raw_text: str,
        source_url: str,
        *,
        max_events: int = 8,
    ) -> list[dict[str, Any]]:
        """Compatibility wrapper for legacy callers."""
        search_results = [
            {
                "title": "Legacy source text",
                "url": source_url,
                "content": raw_text,
            }
        ]
        candidates = asyncio.run(self.extract_events_from_search(search_results))
        return candidates[: max(1, min(int(max_events), 50))]

    def extract_event_data(self, raw_text: str, source_url: str) -> dict:
        """Compatibility wrapper that returns the first extracted event."""
        candidates = self.extract_event_candidates(raw_text, source_url, max_events=1)
        if not candidates:
            return self._default_payload()
        return candidates[0]

    def _build_system_prompt(self) -> str:
        return """You are an expert data extractor for an Arabic NLP research platform.
Extract structured event information from web content.

EXTRACTION RULES:
1. Return ONLY valid JSON (no explanations, no markdown).
2. Return a JSON array of event objects.
3. If the provided text is a short snippet, use your internal knowledge or the URL context to extract as much as possible, or mark fields as [NEEDS RESEARCH] instead of returning null.
4. Do NOT invent or guess dates, locations, or URLs.
5. title_en and description_en must be in English.
6. title_ar and description_ar MUST be real Arabic translations.

CRITICAL ARABIC RULES:
- title_ar: translate title_en to Modern Standard Arabic.
- description_ar: translate description_en to Arabic.
- Use established Arabic NLP terminology.
- Keep technical terms in English when needed:
    transformer, BERT, tokenizer, NLP, embedding, fine-tuning,
    pre-training, corpus, annotation.
- Arabic fields MUST contain Arabic Unicode characters (U+0600-U+06FF).
- NEVER copy English text into Arabic fields.
- If you cannot translate, return null.

OUTPUT FORMAT:
- Return ONLY a JSON array.
- Each object should use this structure:
{
    "title_en": "string or null",
    "title_ar": "Arabic translation or null",
    "description_en": "string, max 500 chars or null",
    "description_ar": "Arabic translation or null",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "location": "City, Country or Online or null",
    "url": "https://... or null",
    "organizer": "string or null",
    "event_type": "conference|workshop|webinar|other or null",
    "language": "arabic|english|multilingual or null",
    "is_arabic_nlp_relevant": true or false,
    "relevance_score": 0.0 to 1.0,
    "extraction_confidence": 0.0 to 1.0,
    "source_url": "must match one input url or null",
    "source_name": "Tavily Search",
    "website": "https://... or null",
    "registration_link": "https://... or null",
    "attachment_url": "https://... or null",
    "banner_image_url": "https://... or null",
    "organizer_name": "string or null",
    "domain": "nlp|speech|computer_vision|ai or null",
    "tags": ["string", "..."] or null
}

RELEVANCE CRITERIA (is_arabic_nlp_relevant=true if):
- Event is about Arabic language processing.
- Event is about NLP/computational linguistics (any language).
- Event is about AI/ML applied to Arabic.
- Event is held in the Arab world.

If no relevant events are found, return an empty JSON array: [].
"""

    def _normalize_search_results(
        self, search_results: list[dict]
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        remaining_content_budget = self.MAX_PROMPT_CONTENT_CHARS_TOTAL

        for result in search_results or []:
            if not isinstance(result, dict):
                continue

            title = (self._normalize_text(result.get("title")) or "")[
                : self.MAX_TITLE_CHARS
            ]
            url = (self._normalize_text(result.get("url")) or "")[: self.MAX_URL_CHARS]

            if url and url in seen_urls:
                continue

            content = self._normalize_text(result.get("content")) or ""
            if content:
                content = content[: self.MAX_CONTENT_CHARS_PER_RESULT]
                if remaining_content_budget <= 0:
                    content = ""
                elif len(content) > remaining_content_budget:
                    content = content[:remaining_content_budget]
                remaining_content_budget -= len(content)

            if not (title or url or content):
                continue

            normalized.append({"title": title, "url": url, "content": content})

            if url:
                seen_urls.add(url)
            if len(normalized) >= self.MAX_PROMPT_RESULTS:
                break

        return normalized

    def _compact_search_results_for_retry(
        self, search_results: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        compact: list[dict[str, str]] = []
        for result in search_results[: self.FALLBACK_PROMPT_RESULTS]:
            title = (result.get("title") or "")[: self.FALLBACK_TITLE_CHARS]
            url = (result.get("url") or "")[: self.FALLBACK_URL_CHARS]
            content = (result.get("content") or "")[: self.FALLBACK_CONTENT_CHARS]
            if not (title or url or content):
                continue
            compact.append({"title": title, "url": url, "content": content})
        return compact

    def _normalize_event(
        self,
        event_item: dict[str, Any],
        allowed_urls: set[str],
    ) -> dict[str, Any] | None:
        del allowed_urls
        source_url = self._normalize_text(
            event_item.get("source_url")
            or event_item.get("event_url")
            or event_item.get("url")
        )
        if not source_url:
            return None

        event = self._default_payload()
        event["title_en"] = self._normalize_title(event_item.get("title_en"))
        event["title_ar"] = self._normalize_title(event_item.get("title_ar"))
        event["description_en"] = self._normalize_description(
            event_item.get("description_en")
        )
        event["description_ar"] = self._normalize_description(
            event_item.get("description_ar")
        )
        event["translation_status"] = infer_translation_status(
            raw_status=event_item.get("translation_status"),
            english_values=[event["title_en"], event["description_en"]],
            arabic_values=[event["title_ar"], event["description_ar"]],
        )
        event["domain"] = self._normalize_domain(event_item.get("domain"))
        raw_type = self._normalize_text(event_item.get("type"))
        event["event_type"] = self._normalize_event_type(
            event_item.get("event_type") or event_item.get("type")
        )
        event["type"] = raw_type or event["event_type"].replace("_", " ").title()
        event["start_date"] = self._normalize_date(event_item.get("start_date"))
        event["end_date"] = self._normalize_date(event_item.get("end_date"))
        event["location"] = self._normalize_location(event_item.get("location"))
        event["source_url"] = source_url
        event["event_url"] = source_url
        event["website"] = self._normalize_url(
            event_item.get("website") or event_item.get("event_url") or source_url
        )
        event["registration_link"] = self._normalize_url(
            event_item.get("registration_link")
        )
        event["attachment_url"] = self._normalize_url(
            event_item.get("attachment_url")
            or event_item.get("file_url")
            or event_item.get("pdf_url")
        )
        event["banner_image_url"] = self._normalize_url(
            event_item.get("banner_image_url")
            or event_item.get("image_url")
            or event_item.get("thumbnail")
        )
        event["organizer_name"] = self._normalize_text(
            event_item.get("organizer_name") or event_item.get("organizer")
        )
        event["tags"] = self._normalize_tags(
            event_item.get("tags") or event_item.get("keywords")
        )
        event["source_name"] = self.SOURCE_NAME

        if not event["title_en"]:
            return None

        # Keep candidates from thin snippets by using an explicit placeholder
        # instead of dropping the entire item.
        if not event["description_en"]:
            event["description_en"] = self.NEEDS_RESEARCH_PLACEHOLDER
        if not event["description_ar"]:
            event["description_ar"] = self.NEEDS_RESEARCH_PLACEHOLDER

        return event

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {
            "title_en": None,
            "title_ar": None,
            "description_en": None,
            "description_ar": None,
            "domain": None,
            "event_type": None,
            "start_date": None,
            "end_date": None,
            "location": None,
            "website": None,
            "registration_link": None,
            "attachment_url": None,
            "banner_image_url": None,
            "organizer_name": None,
            "tags": None,
            "source_url": None,
            "source_name": None,
        }

    @staticmethod
    def _normalize_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "null":
            return None
        return text

    def _normalize_title(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if text is None:
            return None
        return text[:300]

    def _normalize_description(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if text is None:
            return None
        return text[:5000]

    def _normalize_domain(self, value: Any) -> str | None:
        text = self._normalize_text(value)
        if text is None:
            return "nlp"
        lowered = text.lower().replace(" ", "_")
        if lowered in self.DOMAIN_VALUES:
            return lowered
        if lowered in {"computer-vision", "computer vision", "cv"}:
            return "computer_vision"
        if lowered in {"speech", "speech_processing"}:
            return "speech"
        if lowered in {"nlp", "natural_language_processing"}:
            return "nlp"
        if lowered in {"ai", "artificial_intelligence"}:
            return "ai"
        return "nlp"

    def _normalize_event_type(self, value: Any) -> str:
        text = self._normalize_text(value)
        if text is None:
            return "conference"
        lowered = text.lower().replace(" ", "_")
        if lowered in self.EVENT_TYPE_VALUES:
            return lowered
        if lowered in {"call_for_papers", "cfp"}:
            return "conference"
        return "conference"

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        text = LLMEventExtractor._normalize_text(value)
        if text is None:
            return None
        return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else None

    @staticmethod
    def _normalize_location(value: Any) -> str | None:
        text = LLMEventExtractor._normalize_text(value)
        if text is None:
            return "Online"
        return text[:255]

    @staticmethod
    def _normalize_url(value: Any) -> str | None:
        text = LLMEventExtractor._normalize_text(value)
        if text is None:
            return None
        lowered = text.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return None
        return text[:500]

    @staticmethod
    def _normalize_tags(value: Any) -> list[str] | None:
        if value is None:
            return None

        tags: list[str] = []
        if isinstance(value, list):
            for item in value:
                text = LLMEventExtractor._normalize_text(item)
                if text:
                    tags.append(text[:80].lower())
        else:
            text_value = LLMEventExtractor._normalize_text(value)
            if text_value:
                for item in text_value.split(","):
                    text = LLMEventExtractor._normalize_text(item)
                    if text:
                        tags.append(text[:80].lower())

        if not tags:
            return None

        deduped: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            if tag in seen:
                continue
            seen.add(tag)
            deduped.append(tag)

        return deduped

    @staticmethod
    def _strip_code_fences(raw: str) -> str:
        text = (raw or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @staticmethod
    def _extract_json_array_block(text: str) -> str:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return ""
        return match.group(0).strip()

    def _is_rate_limited_response(self) -> bool:
        status_code = getattr(self.client, "last_status_code", None)
        if status_code == 429:
            return True

        message = str(getattr(self.client, "last_error_message", "") or "").lower()
        return (
            "429" in message
            or "too many requests" in message
            or "rate limit" in message
        )

    def _is_payload_too_large_response(self) -> bool:
        status_code = getattr(self.client, "last_status_code", None)
        if status_code == 413:
            return True

        message = str(getattr(self.client, "last_error_message", "") or "").lower()
        return "payload too large" in message or "request entity too large" in message

    @staticmethod
    def _is_rate_limited_exception(exc: Exception) -> bool:
        message = str(exc or "").lower()
        return (
            "429" in message
            or "too many requests" in message
            or "rate limit" in message
        )
