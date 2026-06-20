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

        await asyncio.to_thread(time.sleep, random.uniform(1, 3))
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
        return """You are an expert data extractor for a professional Arabic NLP research platform.
Extract structured information about NLP tools and models from web content.

CRITICAL QUALITY RULES:
1. TITLE must be the CLEAN tool/model name only (e.g. "CAMeL Tools", "AraBERT").
   - REMOVE site suffixes, page metadata, or navigation text.
2. DESCRIPTION must be a CLEAN, PROFESSIONAL SUMMARY (100-400 chars):
   - Write a professional 2-3 sentence summary of what the tool does.
   - NEVER include navigation menus, sidebar links, or raw page content.
3. ONLY extract actual NLP/AI tools and models.
   - REJECT: university pages, blog archives, generic announcements.

EXTRACTION RULES:
1. Return ONLY valid JSON (no explanation, no markdown).
2. Return a JSON array of tool objects.
3. If a field is unknown, return null.
4. Do NOT invent capabilities, licenses, or URLs.
5. title_en and description_en must be in English.
6. title_ar and description_ar MUST be real Arabic translations.

ARABIC RULES:
- Use Modern Standard Arabic.
- NEVER copy English text into Arabic fields.
- Arabic fields must contain Arabic Unicode characters (U+0600-U+06FF).
- Keep technical terms in English when needed:
    transformer, BERT, tokenizer, NLP, embedding, fine-tuning, pre-training.

OUTPUT FORMAT:
[
  {
    "title_en": "Clean tool/model name",
    "title_ar": "Arabic translation or null",
    "description_en": "Clean, professional summary of what it does",
    "description_ar": "Arabic translation or null",
    "github_url": "https://... or null",
    "paper_url": "https://... or null",
    "url": "https://... or null",
    "license": "string or null",
    "capabilities": ["string", "..."] or [],
    "language_support": ["arabic", "english", "multilingual"] or [],
    "is_arabic_nlp_relevant": true or false,
    "relevance_score": 0.0 to 1.0,
    "extraction_confidence": 0.0 to 1.0
  }
]

Return [] if no relevant tools are found.
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

        title_ar = self._pick_text(item, "title_ar") or None
        description_ar = self._pick_text(item, "description_ar") or None

        github_url = self._pick_text(item, "github_url", "github_link")
        paper_url = self._pick_text(
            item,
            "paper_url",
            "documentation_link",
            "url",
        )

        capabilities = self._to_list(item.get("capabilities") or item.get("keywords"))

        translation_status = infer_translation_status(
            raw_status=item.get("translation_status"),
            english_values=[title_en, description_en],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300] if title_ar else None,
            "description_en": description_en[:5000],
            "description_ar": description_ar[:5000] if description_ar else None,
            "github_url": github_url[:500],
            "paper_url": paper_url[:500],
            "license": self._pick_text(item, "license")[:120],
            "capabilities": capabilities,
            "translation_status": translation_status,
            "relevance_score": item.get("relevance_score"),
            "extraction_confidence": item.get("extraction_confidence"),
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
