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


class LLMNewsExtractor:
    """Extract news candidates from Tavily search results using Groq."""

    MAX_PROMPT_RESULTS = 12
    MAX_TITLE_CHARS = 140
    MAX_URL_CHARS = 260
    MAX_CONTENT_CHARS = 320

    RETRY_PROMPT_RESULTS = 4
    RETRY_TITLE_CHARS = 90
    RETRY_URL_CHARS = 180
    RETRY_CONTENT_CHARS = 160

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_news_from_search(self, search_results: list[dict]) -> list[dict]:
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning("LLM news extraction skipped: GROQ key not configured")
            return []

        compact_results = self._compact_search_results(
            normalized_search_results,
            max_results=self.MAX_PROMPT_RESULTS,
            title_chars=self.MAX_TITLE_CHARS,
            url_chars=self.MAX_URL_CHARS,
            content_chars=self.MAX_CONTENT_CHARS,
        )

        user_prompt = json.dumps(
            {"search_results": compact_results},
            ensure_ascii=False,
            default=str,
        )

        await asyncio.to_thread(time.sleep, random.uniform(1, 3))
        try:
            raw_text = await asyncio.to_thread(
                self.client._chat,
                self._system_prompt(),
                user_prompt,
            )
        except Exception as exc:
            logger.warning("LLM news extraction call failed: %s", exc)
            return []

        parsed_items = self._parse_items(raw_text)
        if not parsed_items and getattr(self.client, "last_status_code", None) == 413:
            retry_results = self._compact_search_results(
                normalized_search_results,
                max_results=self.RETRY_PROMPT_RESULTS,
                title_chars=self.RETRY_TITLE_CHARS,
                url_chars=self.RETRY_URL_CHARS,
                content_chars=self.RETRY_CONTENT_CHARS,
            )
            retry_prompt = json.dumps(
                {"search_results": retry_results},
                ensure_ascii=False,
                default=str,
            )

            await asyncio.to_thread(time.sleep, random.uniform(0.8, 1.5))
            try:
                retry_text = await asyncio.to_thread(
                    self.client._chat,
                    self._system_prompt(),
                    retry_prompt,
                )
                parsed_items = self._parse_items(retry_text)
            except Exception as exc:
                logger.warning("LLM news compact retry failed: %s", exc)

        if not parsed_items:
            return self._fallback_items_from_search(normalized_search_results)

        output: list[dict] = []
        for item in parsed_items:
            normalized = self._normalize_item(item)
            if normalized is not None:
                output.append(normalized)
        if output:
            return output
        return self._fallback_items_from_search(normalized_search_results)

    @staticmethod
    def _system_prompt() -> str:
        return """You are an expert data extractor for an Arabic NLP research platform.
Extract structured information for research news and paper announcements.

EXTRACTION RULES:
1. Return ONLY valid JSON (no explanation, no markdown).
2. Return a JSON array of news objects.
3. If unknown, return null.
4. Do NOT invent publication dates or URLs.
5. title_en and summary_en must be in English.
6. title_ar and summary_ar MUST be real Arabic translations.

CRITICAL ARABIC RULES:
- Use Modern Standard Arabic.
- NEVER copy English text into Arabic fields.
- Arabic fields must contain Arabic Unicode characters (U+0600-U+06FF).
- Keep technical terms in English when needed.

OUTPUT FORMAT:
{
  "title_en": "string or null",
  "title_ar": "Arabic translation or null",
  "summary_en": "string or null",
  "summary_ar": "Arabic translation or null",
  "source_url": "https://... or null",
  "published_date": "YYYY-MM-DD or null",
  "tags": ["string", "..."] or [],
  "is_arabic_nlp_relevant": true or false,
  "relevance_score": 0.0 to 1.0,
  "extraction_confidence": 0.0 to 1.0
}

Return [] if no relevant news items are found.
"""

    @staticmethod
    def _normalize_search_results(search_results: list[dict]) -> list[dict[str, str]]:
        output: list[dict[str, str]] = []
        for result in search_results or []:
            if not isinstance(result, dict):
                continue
            title = str(result.get("title") or "").strip()
            url = str(result.get("url") or "").strip()
            content = str(result.get("content") or "").strip()
            if not (title or url or content):
                continue
            output.append({"title": title, "url": url, "content": content})
        return output

    @staticmethod
    def _compact_search_results(
        search_results: list[dict[str, str]],
        *,
        max_results: int,
        title_chars: int,
        url_chars: int,
        content_chars: int,
    ) -> list[dict[str, str]]:
        compact: list[dict[str, str]] = []
        for row in search_results:
            if len(compact) >= max(1, max_results):
                break

            compact.append(
                {
                    "title": str(row.get("title") or "").strip()[: max(20, title_chars)],
                    "url": str(row.get("url") or "").strip()[: max(20, url_chars)],
                    "content": str(row.get("content") or "").strip()[
                        : max(80, content_chars)
                    ],
                }
            )

        return compact

    def _parse_items(self, raw_text: str | None) -> list[dict]:
        if not raw_text:
            return []

        cleaned = self._strip_code_fences(raw_text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            fallback_json = self._extract_json_array_block(cleaned)
            if not fallback_json:
                return []
            try:
                parsed = json.loads(fallback_json)
            except json.JSONDecodeError:
                return []

        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            items = parsed.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
            if parsed:
                return [parsed]
        return []

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1).replace("```", "")
        return cleaned.strip()

    @staticmethod
    def _extract_json_array_block(text: str) -> str:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return ""
        return match.group(0).strip()

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title_en = self._pick_text(item, "title_en", "title", "headline")
        summary_en = self._pick_text(
            item,
            "summary_en",
            "summary",
            "description",
            "content",
        )
        if not title_en or not summary_en:
            return None

        title_ar = self._pick_text(item, "title_ar") or None
        summary_ar = self._pick_text(item, "summary_ar", "description_ar") or None

        source_url = self._pick_text(item, "source_url", "url", "link")
        published_date = self._pick_text(
            item,
            "published_date",
            "publication_date",
            "published_at",
            "date",
        )
        if published_date:
            published_date = published_date[:10]

        tags = self._to_list(
            item.get("tags") or item.get("keywords") or item.get("topics")
        )

        translation_status = infer_translation_status(
            raw_status=item.get("translation_status"),
            english_values=[title_en, summary_en],
            arabic_values=[title_ar, summary_ar],
        )

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300] if title_ar else None,
            "summary_en": summary_en[:5000],
            "summary_ar": summary_ar[:5000] if summary_ar else None,
            "source_url": source_url[:500],
            "published_date": published_date or None,
            "tags": tags,
            "translation_status": translation_status,
        }

    @staticmethod
    def _pick_text(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() != "null":
                return text
        return ""

    @staticmethod
    def _to_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = value.replace(";", ",").split(",")
        else:
            raw_items = [value]

        items: list[str] = []
        for raw in raw_items:
            text = str(raw).strip()
            if not text:
                continue
            items.append(text[:120])
        return items[:20]

    @staticmethod
    def _fallback_items_from_search(
        normalized_search_results: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        keyword_weights = {
            "nlp": 0.25,
            "arabic": 0.2,
            "llm": 0.15,
            "language model": 0.15,
            "transformer": 0.1,
            "dataset": 0.1,
            "paper": 0.1,
            "benchmark": 0.1,
            "conference": 0.08,
            "workshop": 0.08,
            "speech": 0.08,
            "corpus": 0.08,
            "morphology": 0.08,
            "machine translation": 0.08,
            "dialect": 0.08,
        }

        def relevance_score(text: str) -> float:
            haystack = (text or "").lower()
            score = 0.0
            for key, weight in keyword_weights.items():
                if key in haystack:
                    score += weight
            return max(0.0, min(1.0, score))

        fallback: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for row in normalized_search_results:
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            content = str(row.get("content") or "").strip()
            if not title or not content or not url:
                continue
            if not (url.startswith("https://") or url.startswith("http://")):
                continue
            if url in seen_urls:
                continue

            score = relevance_score(f"{title}\n{content}")
            if score < 0.2:
                continue

            seen_urls.add(url)
            fallback.append(
                {
                    "title_en": title[:300],
                    "title_ar": None,
                    "summary_en": content[:5000],
                    "summary_ar": None,
                    "source_url": url[:500],
                    "published_date": None,
                    "tags": [],
                    "translation_status": "missing",
                    "confidence_score": round(score * 100.0, 1),
                }
            )

            if len(fallback) >= 30:
                break

        if fallback:
            logger.info(
                "LLM news extraction fallback produced %d candidate(s)",
                len(fallback),
            )
        return fallback
