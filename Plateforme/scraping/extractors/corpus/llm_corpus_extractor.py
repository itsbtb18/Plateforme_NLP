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


class LLMCorpusExtractor:
    """Extract corpus/dataset candidates from Tavily search results using Groq."""

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_corpus_from_search(
        self, search_results: list[dict]
    ) -> list[dict]:
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning("LLM corpus extraction skipped: GROQ key not configured")
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
            logger.warning("LLM corpus extraction call failed: %s", exc)
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
Extract structured information about corpora and datasets.

CRITICAL QUALITY RULES:
1. DATASET NAME must be the CLEAN corpus/dataset name only (e.g. "Arabic Gigaword", "OSIAN Corpus").
   - REMOVE site suffixes like "| Hugging Face", "- GitHub", "| University Name".
   - REMOVE page metadata, navigation breadcrumbs, or repository paths from names.
   - If the page is a blog listing, author archive, or generic department page (NOT an actual dataset), return [].

2. DESCRIPTION must be a CLEAN, PROFESSIONAL SUMMARY (100-400 chars):
   - Write a professional 2-3 sentence summary describing the dataset, its size, domain, and intended use.
   - NEVER include navigation menus, sidebar links, login forms, cookie notices, footer text.
   - NEVER copy raw HTML page content. Always rewrite into clean prose.

3. STRICT RELEVANCE FILTER:
   - ONLY extract items that are actual NLP/language corpora or datasets.
   - REJECT: university admin announcements, fellowship applications, exam results, general news.
   - Set is_arabic_nlp_relevant=false for irrelevant content.

EXTRACTION RULES:
1. Return ONLY valid JSON (no explanation, no markdown).
2. Return a JSON array of dataset objects.
3. If unknown, return null.
4. Do NOT invent dataset size, license, or URLs.
5. dataset_name and description_en must be in English.
6. title_ar and description_ar MUST be real Arabic translations.

ARABIC RULES:
- Use Modern Standard Arabic.
- NEVER copy English text into Arabic fields.
- Arabic fields must contain Arabic Unicode characters (U+0600-U+06FF).
- Keep technical terms (NLP, corpus, tokenizer, etc.) in English when needed.

OUTPUT FORMAT:
[
  {
    "dataset_name": "Clean dataset/corpus name",
    "title_ar": "Arabic translation or null",
    "description_en": "Clean, professional summary of the dataset",
    "description_ar": "Arabic translation or null",
    "language_variants": ["string", "..."] or [],
    "size_estimate": "string or null",
    "size": "string or null",
    "license": "string or null",
    "download_url": "https://... or null",
    "paper_url": "https://... or null",
    "is_arabic_nlp_relevant": true or false,
    "relevance_score": 0.0 to 1.0,
    "extraction_confidence": 0.0 to 1.0
  }
]

Return [] if no relevant datasets are found.
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
        dataset_name = self._pick_text(item, "dataset_name", "title", "name")
        description_en = self._pick_text(
            item,
            "description_en",
            "description",
            "summary",
            "content",
        )
        if not dataset_name or not description_en:
            return None

        description_ar = self._pick_text(item, "description_ar") or None
        language_variants = self._to_list(
            item.get("language_variants") or item.get("languages")
        )

        download_url = self._pick_text(
            item,
            "download_url",
            "dataset_url",
            "url",
        )
        paper_url = self._pick_text(item, "paper_url", "publication_url")
        translation_status = infer_translation_status(
            raw_status=item.get("translation_status"),
            english_values=[dataset_name, description_en],
            arabic_values=[item.get("title_ar"), description_ar],
        )

        return {
            "dataset_name": dataset_name[:300],
            "description_en": description_en[:5000],
            "description_ar": description_ar[:5000] if description_ar else None,
            "language_variants": language_variants,
            "size_estimate": self._pick_text(item, "size_estimate", "size")[:120],
            "download_url": download_url[:500],
            "paper_url": paper_url[:500],
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
            items.append(text[:80])
        return items[:20]
