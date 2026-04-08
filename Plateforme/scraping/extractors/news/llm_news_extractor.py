from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from scraping.extractors.core.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)


class LLMNewsExtractor:
    """Extract news candidates from Tavily search results using Groq."""

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_news_from_search(self, search_results: list[dict]) -> list[dict]:
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning("LLM news extraction skipped: GROQ key not configured")
            return []

        user_prompt = json.dumps(
            {"search_results": normalized_search_results},
            ensure_ascii=False,
            default=str,
        )

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
        if not parsed_items:
            return []

        output: list[dict] = []
        for item in parsed_items:
            normalized = self._normalize_item(item)
            if normalized is not None:
                output.append(normalized)
        return output

    @staticmethod
    def _system_prompt() -> str:
        return """You are a strict extraction assistant for Arabic NLP news and papers.
You receive search_results as JSON array entries (title/url/content).
Return ONLY a JSON array and no markdown.
Each output item should include these keys:
- title_en
- title_ar
- summary_en
- summary_ar
- source_url
- published_date
- tags
Rules:
- Keep only NLP/AI research news and publication items.
- published_date should be YYYY-MM-DD when possible, else null.
- tags must be an array of short strings.
- If a field is unknown, return null.
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

    def _parse_items(self, raw_text: str | None) -> list[dict]:
        if not raw_text:
            return []

        cleaned = self._strip_code_fences(raw_text)
        try:
            parsed = json.loads(cleaned)
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

        title_ar = self._pick_text(item, "title_ar") or title_en
        summary_ar = self._pick_text(item, "summary_ar", "description_ar") or summary_en

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

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300],
            "summary_en": summary_en[:5000],
            "summary_ar": summary_ar[:5000],
            "source_url": source_url[:500],
            "published_date": published_date or None,
            "tags": tags,
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
