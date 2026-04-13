from __future__ import annotations

import logging
import time
from typing import Any

from scraping.extractors.core.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)


class ArabicTranslator:
    """Unified Arabic translation service for scraped candidates."""

    SUPPORTED_FIELD_TYPES = {"title", "description", "short_description", "tags"}

    _PROMPT_TEMPLATE = (
        "You are an expert Arabic translator specializing in NLP and AI research terminology.\n"
        "Translate the following {field_type} from English to Modern Standard Arabic (MSA).\n"
        "Preserve technical terms in English when no established Arabic equivalent exists.\n"
        "Return ONLY the Arabic translation, no explanation."
    )

    def __init__(self):
        from django.conf import settings

        primary_key = str(getattr(settings, "GROQ_SCRAPING_API_KEY", "") or "").strip()
        fallback_key = str(getattr(settings, "GROQ_INTERNAL_API_KEY", "") or "").strip()

        primary_model = str(
            getattr(settings, "GROQ_SCRAPING_MODEL", "llama-3.3-70b-versatile")
            or "llama-3.3-70b-versatile"
        ).strip()
        fallback_model = str(
            getattr(settings, "GROQ_INTERNAL_MODEL", primary_model) or primary_model
        ).strip()

        self.primary_client = GroqLLMClient(api_key=primary_key, model=primary_model)
        self.fallback_client = GroqLLMClient(api_key=fallback_key, model=fallback_model)

        self.max_retries = max(
            1,
            int(getattr(settings, "SCRAPING_TRANSLATION_MAX_RETRIES", 3) or 3),
        )
        self.backoff_initial_seconds = max(
            0.25,
            float(
                getattr(settings, "SCRAPING_TRANSLATION_BACKOFF_INITIAL_SECONDS", 1.0)
                or 1.0
            ),
        )
        self.backoff_max_seconds = max(
            self.backoff_initial_seconds,
            float(
                getattr(settings, "SCRAPING_TRANSLATION_BACKOFF_MAX_SECONDS", 8.0)
                or 8.0
            ),
        )

        self._rate_limited = False

    def translate_field(self, text_en: str, field_type: str) -> str | None:
        """Translate one English field to Arabic; returns None on failure."""
        normalized_text = self._clean_text(text_en)
        if not normalized_text:
            return None

        normalized_field_type = str(field_type or "").strip().lower()
        if normalized_field_type not in self.SUPPORTED_FIELD_TYPES:
            logger.warning("translation_field_type_unsupported type=%s", field_type)
            return None

        if self._contains_arabic(normalized_text):
            # Already Arabic enough, do not call external API.
            return normalized_text

        system_prompt = self._PROMPT_TEMPLATE.format(field_type=normalized_field_type)
        response = self._chat_with_fallback(system_prompt, normalized_text)
        if not response:
            return None

        translated = self._clean_text(self._strip_code_fences(response))
        if not translated:
            logger.warning(
                "translation_empty_response field_type=%s", normalized_field_type
            )
            return None

        if not self._contains_arabic(translated):
            logger.warning(
                "translation_non_arabic_response field_type=%s sample=%s",
                normalized_field_type,
                translated[:80],
            )
            return None

        return translated

    def translate_item(self, item: dict, fields_to_translate: list[str]) -> dict:
        """Translate configured fields for one candidate and set translation_status."""
        translated_item = dict(item or {})
        if not fields_to_translate:
            translated_item["translation_status"] = "translated"
            return translated_item

        translated_count = 0
        failed_count = 0

        for field in self._dedupe_preserve_order(fields_to_translate):
            if not field:
                continue

            target_field = str(field).strip()
            if not target_field:
                continue

            existing_value = self._clean_text(translated_item.get(target_field))
            if existing_value and self._contains_arabic(existing_value):
                translated_count += 1
                continue

            source_text = self._resolve_source_text(translated_item, target_field)
            if not source_text:
                continue

            field_type = self._infer_field_type(target_field)
            translated_value = self.translate_field(source_text, field_type)
            if translated_value:
                for destination_key in self._destination_keys(target_field):
                    translated_item[destination_key] = translated_value
                translated_count += 1
            else:
                failed_count += 1
                logger.warning(
                    "translation_field_failed field=%s source_hint=%s",
                    target_field,
                    source_text[:80],
                )

        if translated_count > 0 and failed_count == 0:
            status = "translated"
        elif translated_count > 0 and failed_count > 0:
            status = "partial"
        elif failed_count > 0:
            status = "failed"
        else:
            status = "translated"

        translated_item["translation_status"] = status
        return translated_item

    def batch_translate(self, items: list[dict], fields: list[str]) -> list[dict]:
        """Translate a batch of candidates with exponential backoff on rate limits."""
        translated_items: list[dict] = []
        for index, item in enumerate(items or [], start=1):
            delay = self.backoff_initial_seconds
            last_result: dict | None = None

            for attempt in range(1, self.max_retries + 1):
                self._rate_limited = False
                try:
                    last_result = self.translate_item(item, fields)
                except Exception as exc:
                    logger.warning(
                        "translation_item_exception index=%s attempt=%s error=%s",
                        index,
                        attempt,
                        exc,
                    )
                    last_result = dict(item or {})
                    last_result["translation_status"] = "failed"

                if self._rate_limited and attempt < self.max_retries:
                    logger.warning(
                        "translation_rate_limited index=%s attempt=%s/%s backoff=%.2fs",
                        index,
                        attempt,
                        self.max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2.0, self.backoff_max_seconds)
                    continue

                break

            if last_result is None:
                last_result = dict(item or {})
                last_result["translation_status"] = "failed"

            if last_result.get("translation_status") in {"failed", "partial"}:
                logger.warning(
                    "translation_item_incomplete index=%s status=%s",
                    index,
                    last_result.get("translation_status"),
                )

            translated_items.append(last_result)

        return translated_items

    def _chat_with_fallback(self, system_prompt: str, user_prompt: str) -> str | None:
        clients = [
            ("groq_scraping", self.primary_client),
            ("groq_internal", self.fallback_client),
        ]

        for label, client in clients:
            if client is None or not client.is_configured:
                continue

            response = client._chat(system_prompt, user_prompt)
            status = int(client.last_status_code or 0)
            if status == 429:
                self._rate_limited = True
                logger.warning("translation_api_rate_limited client=%s", label)
            elif status in {413}:
                logger.warning("translation_api_payload_too_large client=%s", label)

            if response:
                return response

        return None

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    @staticmethod
    def _contains_arabic(text: str) -> bool:
        return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1).replace("```", "")
        return cleaned.strip()

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values or []:
            normalized = str(value or "").strip()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)
        return output

    def _infer_field_type(self, target_field: str) -> str:
        key = str(target_field or "").lower()
        if "short_description" in key or "summary" in key:
            return "short_description"
        if "tag" in key:
            return "tags"
        if "title" in key or "name" in key:
            return "title"
        return "description"

    def _resolve_source_text(self, item: dict[str, Any], target_field: str) -> str:
        target = str(target_field or "").strip()
        if not target:
            return ""

        candidates_by_target = {
            "title_ar": ["title_en", "title", "job_title", "dataset_name"],
            "description_ar": [
                "description_en",
                "summary_en",
                "content_en",
                "description",
            ],
            "short_description_ar": [
                "short_description_en",
                "summary_en",
                "description_en",
                "content_en",
            ],
            "summary_ar": ["summary_en", "description_en", "content_en"],
            "content_ar": ["content_en", "summary_en", "description_en"],
            "tags_ar": ["tags", "keywords"],
        }

        source_keys = list(candidates_by_target.get(target, []))

        if target.endswith("_ar"):
            base = target[: -len("_ar")]
            source_keys.extend([f"{base}_en", base])
        else:
            source_keys.append(target)

        for source_key in self._dedupe_preserve_order(source_keys):
            value = item.get(source_key)
            if isinstance(value, list):
                joined = ", ".join(
                    self._clean_text(v) for v in value if self._clean_text(v)
                )
                if joined:
                    return joined
                continue
            text = self._clean_text(value)
            if text:
                return text

        return ""

    @staticmethod
    def _destination_keys(target_field: str) -> list[str]:
        aliases = {
            "content_ar": ["content_ar", "summary_ar"],
            "summary_ar": ["summary_ar", "content_ar"],
            "description_ar": ["description_ar", "summary_ar"],
        }
        return aliases.get(target_field, [target_field])
