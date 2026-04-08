from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from scraping.extractors.core.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)


class LLMToolExtractor:
    """Extract tool candidates from Tavily search results using Groq."""

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_tools_from_search(self, search_results: list[dict]) -> list[dict]:
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning("LLM tool extraction skipped: GROQ key not configured")
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
            logger.warning("LLM tool extraction call failed: %s", exc)
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
        return """You are a strict extraction assistant for Arabic NLP tools.
You receive search_results as JSON array entries (title/url/content).
Return ONLY a JSON array and no markdown.
Each output item should include these keys:
- title_en
- title_ar
- description_en
- description_ar
- github_url
- paper_url
- license
- capabilities
Rules:
- Keep only real NLP/AI tools.
- If a field is unknown, return null.
- capabilities must be an array of short strings.
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
        title_en = self._pick_text(item, "title_en", "title", "name")
        description_en = self._pick_text(
            item,
            "description_en",
            "description",
            "summary",
            "what_it_does",
        )
        if not title_en or not description_en:
            return None

        title_ar = self._pick_text(item, "title_ar") or title_en
        description_ar = self._pick_text(item, "description_ar") or description_en

        github_url = self._pick_text(item, "github_url", "github_link")
        paper_url = self._pick_text(
            item,
            "paper_url",
            "documentation_link",
            "url",
        )

        capabilities = self._to_list(item.get("capabilities") or item.get("keywords"))

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300],
            "description_en": description_en[:5000],
            "description_ar": description_ar[:5000],
            "github_url": github_url[:500],
            "paper_url": paper_url[:500],
            "license": self._pick_text(item, "license")[:120],
            "capabilities": capabilities,
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
