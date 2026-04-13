"""Tavily + Groq based corpus scraper."""

from __future__ import annotations

import logging
import time
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps as django_apps
from django.utils import timezone

from scraping.extractors.corpus.llm_corpus_extractor import LLMCorpusExtractor
from scraping.field_mapping import get_auto_translate_fields
from scraping.network.search_client import TavilySearchClient
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

from .base import BaseScraper

logger = logging.getLogger(__name__)


class CorpusScraper(BaseScraper):
    """Discover Arabic NLP datasets/corpora from web search and LLM extraction."""

    name = "Arabic NLP Corpora (Tavily + Groq)"
    category = "corpus"
    API_CALL_DELAY_SECONDS = 2

    MODEL_CANDIDATES = (
        ("events", "Corpus"),
        ("resources", "Corpus"),
        ("corpus", "Corpus"),
    )

    def scrape(self):
        model = self._resolve_model()
        if model is None:
            self._log_error(
                "corpus_model_missing",
                "No Corpus model found in configured model candidates",
                source=self.name,
            )
            return

        try:
            search_client = TavilySearchClient()
            extractor = LLMCorpusExtractor()
        except Exception as exc:
            self._log_error("corpus_init_failed", str(exc), source=self.name)
            logger.warning("Corpus scraper initialization failed: %s", exc)
            return

        if not search_client.is_enabled:
            self._log_error(
                "corpus_search_unavailable",
                search_client.disabled_reason or "Tavily search client unavailable",
                source=self.name,
            )
            return

        search_queries = self.get_active_search_queries(self.category)
        if not search_queries:
            logger.warning(
                "No active search queries configured for category '%s'.", self.category
            )
            return

        combined_results: list[dict] = []
        total_queries = len(search_queries)
        self.emit_progress(
            "discovery",
            0,
            total_queries,
            "🔍 Starting discovery...",
            current_source=self.name,
        )
        for query_index, query in enumerate(search_queries, start=1):
            self.emit_progress(
                "discovery",
                query_index,
                total_queries,
                f"🔍 Searching: {query}",
                current_source=query,
                current_item=query,
            )
            try:
                time.sleep(self.API_CALL_DELAY_SECONDS)
                results = async_to_sync(search_client.search_corpus)(query)
            except Exception as exc:
                self._log_error(
                    "corpus_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                combined_results.extend(results)

        if not combined_results:
            logger.warning("No corpus search results returned by Tavily.")
            return

        try:
            time.sleep(self.API_CALL_DELAY_SECONDS)
            total_batches = 1
            self.emit_progress(
                "extraction",
                0,
                total_batches,
                "🤖 Starting extraction...",
                current_item="Batch 0/1",
            )
            self.emit_progress(
                "extraction",
                1,
                total_batches,
                "🤖 Extracting batch 1/1",
                current_item="Batch 1/1",
            )
            candidates = async_to_sync(extractor.extract_corpus_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("corpus_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No corpus candidates extracted from Tavily results.")
            return

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            *get_auto_translate_fields(self.category),
        ]
        candidates = translator.batch_translate(candidates, fields=fields_to_translate)

        fields = self._model_fields(model)
        author = self._resolve_system_user_if_needed(fields)

        total_candidates = len(candidates)
        self.emit_progress(
            "validation",
            0,
            total_candidates,
            "✅ Starting validation...",
        )
        for candidate_index, candidate in enumerate(candidates, start=1):
            self.emit_progress(
                "saving",
                candidate_index,
                total_candidates,
                f"💾 Saving item {candidate_index}/{total_candidates}",
                current_item=(
                    str(
                        candidate.get("dataset_name")
                        or candidate.get("title_en")
                        or candidate.get("title")
                        or ""
                    ).strip()
                    if isinstance(candidate, dict)
                    else ""
                ),
            )
            if not isinstance(candidate, dict):
                self.items_skipped += 1
                continue

            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                self.items_skipped += 1
                continue

            if not self.passes_min_confidence_to_save(normalized):
                self.items_skipped += 1
                continue

            lookup = self._build_lookup(fields, normalized)
            if lookup is None:
                self._log_error(
                    "corpus_lookup_unavailable",
                    "No compatible unique lookup field found for model",
                    source=self.name,
                    url=normalized.get("download_url") or "",
                )
                self.items_skipped += 1
                continue

            defaults = self._build_defaults(fields, normalized, author)

            try:
                obj, created = model.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
            except Exception as exc:
                self._log_error(
                    "corpus_upsert_failed",
                    str(exc),
                    source=normalized["dataset_name"],
                    url=normalized.get("download_url") or "",
                )
                self.items_skipped += 1
                continue

            if created:
                self._set_creation_flags(model, obj.pk, fields)
                self.items_created += 1
            else:
                self.items_updated += 1

            self.results.append(
                {
                    "title": normalized["dataset_name"],
                    "description": self.truncate(normalized["description_en"], 400),
                    "type": "corpus",
                    "url": normalized.get("download_url")
                    or normalized.get("paper_url")
                    or "",
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized.get("download_url")
                    or normalized.get("paper_url")
                    or "",
                    "title_en": normalized["dataset_name"],
                    "title_ar": normalized.get("title_ar"),
                    "description_en": normalized["description_en"],
                    "description_ar": normalized.get("description_ar"),
                    "dataset_name": normalized["dataset_name"],
                    "download_url": normalized.get("download_url"),
                    "paper_url": normalized.get("paper_url"),
                    "language_variants": normalized.get("language_variants") or [],
                    "size_estimate": normalized.get("size_estimate"),
                    "translation_status": normalized.get(
                        "translation_status", "pending"
                    ),
                }
            )

    def _resolve_model(self):
        for app_label, model_name in self.MODEL_CANDIDATES:
            try:
                model = django_apps.get_model(app_label, model_name)
            except LookupError:
                continue
            if model is not None:
                return model
        return None

    @staticmethod
    def _model_fields(model) -> set[str]:
        return {
            field.name
            for field in model._meta.get_fields()
            if getattr(field, "concrete", False)
        }

    def _resolve_system_user_if_needed(self, fields: set[str]):
        if "author" in fields or "created_by" in fields:
            try:
                return self.get_system_user()
            except Exception as exc:
                logger.warning("System user unavailable for corpus scraper: %s", exc)
        return None

    def _build_lookup(self, fields: set[str], item: dict[str, Any]):
        download_url = item.get("download_url")
        if download_url:
            for candidate in ("download_url", "url", "source_url", "access_link"):
                if candidate in fields:
                    return {candidate: download_url}

        for candidate in ("dataset_name", "title_en", "title", "name"):
            if candidate in fields:
                return {candidate: item["dataset_name"]}

        return None

    def _build_defaults(
        self,
        fields: set[str],
        item: dict[str, Any],
        author,
    ) -> dict[str, Any]:
        defaults: dict[str, Any] = {}

        self._set_if_present(defaults, fields, "dataset_name", item["dataset_name"])
        self._set_if_present(defaults, fields, "title", item["dataset_name"])
        self._set_if_present(defaults, fields, "title_en", item["dataset_name"])
        self._set_if_present(defaults, fields, "title_ar", item.get("title_ar"))
        self._set_if_present(defaults, fields, "description", item["description_en"])
        self._set_if_present(defaults, fields, "description_en", item["description_en"])
        self._set_if_present(defaults, fields, "description_ar", item["description_ar"])
        self._set_if_present(
            defaults, fields, "size_estimate", item.get("size_estimate")
        )

        download_url = item.get("download_url")
        paper_url = item.get("paper_url")
        primary_url = download_url or paper_url
        if primary_url:
            self._set_if_present(defaults, fields, "url", primary_url)
            self._set_if_present(defaults, fields, "source_url", primary_url)
            self._set_if_present(defaults, fields, "access_link", primary_url)

        if download_url:
            self._set_if_present(defaults, fields, "download_url", download_url)
        if paper_url:
            self._set_if_present(defaults, fields, "paper_url", paper_url)

        language_variants = item.get("language_variants") or []
        if language_variants:
            self._set_if_present(
                defaults, fields, "language_variants", language_variants
            )
            self._set_if_present(
                defaults, fields, "keywords", ", ".join(language_variants)
            )

        if "entities" in fields:
            defaults["entities"] = {
                "language_variants": language_variants,
                "size_estimate": item.get("size_estimate"),
                "paper_url": paper_url,
            }
        if "source_name" in fields:
            defaults["source_name"] = "Tavily Search + Groq"
        if "language" in fields:
            defaults["language"] = "ar"
        if "update_date" in fields:
            defaults["update_date"] = timezone.now()
        if "author" in fields and author is not None:
            defaults["author"] = author
        if "created_by" in fields and author is not None:
            defaults["created_by"] = author

        return defaults

    @staticmethod
    def _set_if_present(
        defaults: dict[str, Any],
        fields: set[str],
        key: str,
        value: Any,
    ):
        if key not in fields:
            return
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        defaults[key] = value

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    def _normalize_candidate(self, item: dict[str, Any]) -> dict[str, Any] | None:
        dataset_name = self._safe_text(item.get("dataset_name"))
        description_en = self._safe_text(item.get("description_en"))
        if not dataset_name or not description_en:
            return None

        description_ar = self._safe_text(item.get("description_ar")) or None

        language_variants_raw = item.get("language_variants")
        language_variants: list[str] = []
        if isinstance(language_variants_raw, list):
            language_variants = [
                str(value).strip()[:80]
                for value in language_variants_raw
                if str(value).strip()
            ]
        elif isinstance(language_variants_raw, str):
            language_variants = [
                chunk.strip()[:80]
                for chunk in language_variants_raw.replace(";", ",").split(",")
                if chunk.strip()
            ]

        title_ar = self._safe_text(item.get("title_ar"))[:300] or None
        translation_status = infer_translation_status(
            raw_status=self._safe_text(item.get("translation_status")) or "pending",
            english_values=[dataset_name, description_en],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "dataset_name": dataset_name[:300],
            "title_ar": title_ar,
            "description_en": description_en[:5000],
            "description_ar": description_ar[:5000] if description_ar else None,
            "language_variants": language_variants,
            "size_estimate": self._safe_text(item.get("size_estimate"))[:120] or None,
            "download_url": self._safe_text(item.get("download_url"))[:500],
            "paper_url": self._safe_text(item.get("paper_url"))[:500],
            "translation_status": translation_status,
        }

    @staticmethod
    def _set_creation_flags(model, pk, fields: set[str]):
        updates: dict[str, Any] = {}
        if "approval_status" in fields:
            updates["approval_status"] = "pending"
        if "source" in fields:
            updates["source"] = "scrape"
        if "is_approved" in fields:
            updates["is_approved"] = False

        if updates:
            model.objects.filter(pk=pk).update(**updates)
