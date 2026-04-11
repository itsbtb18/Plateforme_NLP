from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from scraping.extractors.core.llm_validation import GroqLLMClient
from scraping.utils import infer_translation_status

logger = logging.getLogger(__name__)


class LLMOpportunityExtractor:
    """Extract opportunity candidates from Tavily search results using Groq."""

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    async def extract_opportunities_from_search(
        self, search_results: list[dict]
    ) -> list[dict]:
        normalized_search_results = self._normalize_search_results(search_results)
        if not normalized_search_results:
            return []

        if not self.client.is_configured:
            logger.warning(
                "LLM opportunity extraction skipped: GROQ key not configured"
            )
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
            logger.warning("LLM opportunity extraction call failed: %s", exc)
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
        return """You are an expert data extractor for an Arabic NLP research platform.
    Extract structured information about opportunities (jobs, PhD, postdoc, grants).

    EXTRACTION RULES:
    1. Return ONLY valid JSON (no explanation, no markdown).
    2. Return a JSON array of opportunity objects.
    3. If unknown, return null.
    4. Do NOT invent deadlines, institutions, or URLs.
    5. job_title and description must be in English.
    6. title_ar and description_ar MUST be real Arabic translations.

    CRITICAL ARABIC RULES:
    - Use Modern Standard Arabic.
    - NEVER copy English text into Arabic fields.
    - Arabic fields must contain Arabic Unicode characters (U+0600-U+06FF).
    - Keep technical terms in English when needed.

    OUTPUT FORMAT:
    {
      "job_title": "string or null",
      "title_ar": "Arabic translation or null",
      "institution_name": "string or null",
      "opportunity_type": "Job|Phd|PostDoc|Grant or null",
      "deadline": "YYYY-MM-DD or null",
      "location": "City, Country or Online or null",
      "url": "https://... or null",
      "description": "string or null",
      "description_ar": "Arabic translation or null",
      "is_arabic_nlp_relevant": true or false,
      "relevance_score": 0.0 to 1.0,
      "extraction_confidence": 0.0 to 1.0
    }

    Return [] if no relevant opportunities are found.
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
        job_title = self._pick_text(item, "job_title", "title", "name")
        institution_name = self._pick_text(
            item,
            "institution_name",
            "institution",
            "organization",
            "company",
        )
        description = self._pick_text(
            item,
            "description",
            "summary",
            "content",
        )
        if not job_title or not institution_name or not description:
            return None

        title_ar = self._pick_text(item, "title_ar", "job_title_ar") or None
        description_ar = self._pick_text(item, "description_ar") or None
        translation_status = infer_translation_status(
            raw_status=item.get("translation_status"),
            english_values=[job_title, description],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "job_title": job_title[:300],
            "title_ar": title_ar[:300] if title_ar else None,
            "institution_name": institution_name[:255],
            "opportunity_type": self._normalize_type(item.get("opportunity_type")),
            "deadline": self._normalize_date(item.get("deadline")),
            "location": self._pick_text(item, "location")[:255] or "Online",
            "url": self._pick_text(item, "url", "source_url", "link")[:500],
            "description": description[:5000],
            "description_ar": description_ar[:5000] if description_ar else None,
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
    def _normalize_type(value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"phd", "ph.d", "doctorate"}:
            return "Phd"
        if text in {"postdoc", "post-doc", "postdoctoral", "post doc"}:
            return "PostDoc"
        if text in {"grant", "funding", "fellowship", "scholarship"}:
            return "Grant"
        return "Job"

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        text = str(value or "").strip()
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return text
        return None
