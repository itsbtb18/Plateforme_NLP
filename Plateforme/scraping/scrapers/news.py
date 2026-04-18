"""Tavily + Groq based news scraper."""

from __future__ import annotations

import logging
import time
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps as django_apps
from django.db import transaction
from django.utils import timezone

from scraping.extractors.news.llm_news_extractor import LLMNewsExtractor
from scraping.field_mapping import get_auto_translate_fields
from scraping.network.search_client import TavilySearchClient
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

from .base import BaseScraper

logger = logging.getLogger(__name__)


class NewsScraper(BaseScraper):
    """Discover Arabic NLP news from web search and LLM extraction."""

    name = "Arabic NLP News (Tavily + Groq)"
    category = "news"
    API_CALL_DELAY_SECONDS = 2
    STATUS_CONFIDENCE_DELTA = 0.15

    MODEL_CANDIDATES = (
        ("QA", "Post"),
        ("events", "News"),
        ("resources", "News"),
        ("feed", "Post"),
    )

    def scrape(self):
        model = self._resolve_model()
        if model is None:
            self._log_error(
                "news_model_missing",
                "No News model found in configured model candidates",
                source=self.name,
            )
            return

        try:
            search_client = TavilySearchClient()
            extractor = LLMNewsExtractor()
        except Exception as exc:
            self._log_error("news_init_failed", str(exc), source=self.name)
            logger.warning("News scraper initialization failed: %s", exc)
            return

        if not search_client.is_enabled:
            self._log_error(
                "news_search_unavailable",
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
                results = async_to_sync(search_client.search_news)(query)
            except Exception as exc:
                self._log_error(
                    "news_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                combined_results.extend(results)

        if not combined_results:
            logger.warning("No news search results returned by Tavily.")
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
            candidates = async_to_sync(extractor.extract_news_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("news_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No news candidates extracted from Tavily results.")
            return

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            "summary_ar",
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
                        candidate.get("title_en") or candidate.get("title") or ""
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
                    "news_lookup_unavailable",
                    "No compatible unique lookup field found for model",
                    source=self.name,
                    url=normalized.get("source_url") or "",
                )
                self.items_skipped += 1
                continue

            defaults = self._build_defaults(fields, normalized, author)
            now = timezone.now()

            try:
                with transaction.atomic():
                    obj = model.objects.select_for_update().filter(**lookup).first()
                    if obj is not None:
                        if "last_scraped_at" in fields:
                            defaults["last_scraped_at"] = now
                        if "update_counter" in fields:
                            defaults["update_counter"] = (
                                int(getattr(obj, "update_counter", 0) or 0) + 1
                            )
                        existing_status = str(
                            getattr(obj, "scrape_status", "") or ""
                        ).upper()
                        if self._is_terminal_review_status(existing_status):
                            defaults = self._build_terminal_status_update_defaults(
                                existing_obj=obj,
                                incoming_defaults=defaults,
                                metadata_fields={
                                    "last_scraped_at",
                                    "update_counter",
                                    "update_date",
                                },
                            )
                        elif (
                            str(defaults.get("scrape_status") or "").upper()
                            == "REJECTED"
                        ):
                            defaults["scrape_status"] = "REJECTED"
                            defaults["validation_notes"] = self._append_validation_note(
                                str(defaults.get("validation_notes") or ""),
                                "Auto-marked REJECTED due to confidence_score below 50%.",
                            )
                        else:
                            defaults["scrape_status"] = "PENDING_REVIEW"

                        for field_name, field_value in defaults.items():
                            setattr(obj, field_name, field_value)
                        obj.save()
                        created = False
                    else:
                        semantic_queryset = self._recent_dedup_queryset(
                            model.objects.only("id", "title", "title_en")
                        )
                        semantic_obj, semantic_score = self._find_semantic_title_match(
                            semantic_queryset,
                            normalized["title_en"],
                            title_fields=("title_en", "title"),
                        )
                        if semantic_obj is not None:
                            obj = semantic_obj
                            defaults["last_scraped_at"] = now
                            defaults["update_counter"] = (
                                int(getattr(obj, "update_counter", 0) or 0) + 1
                            )
                            existing_status = str(
                                getattr(obj, "scrape_status", "") or ""
                            ).upper()
                            if self._is_terminal_review_status(existing_status):
                                defaults = self._build_terminal_status_update_defaults(
                                    existing_obj=obj,
                                    incoming_defaults=defaults,
                                    metadata_fields={
                                        "last_scraped_at",
                                        "update_counter",
                                        "update_date",
                                    },
                                )
                            for field_name, field_value in defaults.items():
                                setattr(obj, field_name, field_value)
                            obj.save()
                            created = False
                        else:
                        defaults.setdefault("scrape_status", "PENDING_REVIEW")
                        if "last_scraped_at" in fields:
                            defaults["last_scraped_at"] = now
                        if "update_counter" in fields:
                            defaults.setdefault("update_counter", 0)
                        create_data = dict(defaults)
                        create_data.update(lookup)
                        obj = model.objects.create(**create_data)
                        created = True
            except Exception as exc:
                self._log_error(
                    "news_upsert_failed",
                    str(exc),
                    source=normalized["title_en"],
                    url=normalized.get("source_url") or "",
                )
                self.items_skipped += 1
                continue

            if created:
                self._set_creation_flags(model, obj.pk, fields)
                self.items_created += 1
            else:
                self.items_updated += 1
            self._track_saved_item_status(defaults)

            self.results.append(
                {
                    "title": normalized["title_en"],
                    "description": self.truncate(normalized["summary_en"], 400),
                    "type": "news",
                    "url": normalized.get("source_url") or "",
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized.get("source_url") or "",
                    "title_en": normalized["title_en"],
                    "title_ar": normalized["title_ar"],
                    "description_en": normalized["summary_en"],
                    "description_ar": normalized["summary_ar"],
                    "published_date": normalized.get("published_date"),
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
                logger.warning("System user unavailable for news scraper: %s", exc)
        return None

    def _build_lookup(self, fields: set[str], item: dict[str, Any]):
        source_url = item.get("source_url")
        if source_url:
            for candidate in ("source_url", "url", "access_link"):
                if candidate in fields:
                    return {candidate: source_url}

        for candidate in ("title_en", "title", "headline", "name"):
            if candidate in fields:
                return {candidate: item["title_en"]}

        return None

    def _build_defaults(
        self,
        fields: set[str],
        item: dict[str, Any],
        author,
    ) -> dict[str, Any]:
        defaults: dict[str, Any] = {}

        self._set_if_present(defaults, fields, "title", item["title_en"])
        self._set_if_present(defaults, fields, "title_en", item["title_en"])
        self._set_if_present(defaults, fields, "title_ar", item["title_ar"])
        self._set_if_present(defaults, fields, "description", item["summary_en"])
        self._set_if_present(defaults, fields, "description_en", item["summary_en"])
        self._set_if_present(defaults, fields, "description_ar", item["summary_ar"])
        self._set_if_present(defaults, fields, "summary", item["summary_en"])
        self._set_if_present(defaults, fields, "summary_en", item["summary_en"])
        self._set_if_present(defaults, fields, "summary_ar", item["summary_ar"])
        self._set_if_present(defaults, fields, "content", item["summary_en"])
        self._set_if_present(defaults, fields, "content_en", item["summary_en"])
        self._set_if_present(defaults, fields, "content_ar", item["summary_ar"])

        if item.get("source_url"):
            self._set_if_present(defaults, fields, "source_url", item["source_url"])
            self._set_if_present(defaults, fields, "url", item["source_url"])
            self._set_if_present(defaults, fields, "access_link", item["source_url"])

        if item.get("published_date"):
            self._set_if_present(
                defaults, fields, "published_date", item["published_date"]
            )
            self._set_if_present(defaults, fields, "date", item["published_date"])

        tags = item.get("tags") or []
        if tags:
            self._set_if_present(defaults, fields, "keywords", ", ".join(tags))
            self._set_if_present(defaults, fields, "tags", tags)

        if "entities" in fields:
            defaults["entities"] = {
                "tags": tags,
                "published_date": item.get("published_date"),
            }
        if "source_name" in fields:
            defaults["source_name"] = "Tavily Search + Groq"
        if "language" in fields:
            defaults["language"] = (
                "ar"
                if self._contains_arabic(
                    (item.get("title_ar") or "") + " " + (item.get("summary_ar") or "")
                )
                else "en"
            )
        if "update_date" in fields:
            defaults["update_date"] = timezone.now()
        if "scrape_status" in fields:
            defaults["scrape_status"] = str(
                item.get("scrape_status") or "PENDING_REVIEW"
            ).upper()
        if "validation_notes" in fields:
            defaults["validation_notes"] = str(item.get("validation_notes") or "")
        if "confidence_score" in fields:
            defaults["confidence_score"] = self._normalize_confidence(
                item.get("confidence_score")
            )
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
    def _contains_arabic(text: str) -> bool:
        return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    def _normalize_candidate(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title_en = self._safe_text(item.get("title_en"))
        summary_en = self._safe_text(item.get("summary_en"))
        if not title_en:
            return None
        if not summary_en:
            summary_en = "[NEEDS RESEARCH]"

        title_ar = self._safe_text(item.get("title_ar")) or None
        summary_ar = self._safe_text(item.get("summary_ar")) or None

        tags_raw = item.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [
                str(value).strip()[:120] for value in tags_raw if str(value).strip()
            ]
        elif isinstance(tags_raw, str):
            tags = [
                chunk.strip()[:120]
                for chunk in tags_raw.replace(";", ",").split(",")
                if chunk.strip()
            ]

        translation_status = infer_translation_status(
            raw_status=self._safe_text(item.get("translation_status")) or "pending",
            english_values=[title_en, summary_en],
            arabic_values=[title_ar, summary_ar],
        )

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300] if title_ar else None,
            "summary_en": summary_en[:5000],
            "summary_ar": summary_ar[:5000] if summary_ar else None,
            "source_url": (
                self._safe_text(item.get("source_url"))
                or self._safe_text(item.get("url"))
                or self._safe_text(item.get("access_link"))
                or "[NEEDS RESEARCH]"
            )[:500],
            "published_date": self._safe_text(item.get("published_date"))[:10] or None,
            "tags": tags,
            "confidence_score": self._normalize_confidence(
                item.get("confidence_score", item.get("extraction_confidence"))
            ),
            "translation_status": translation_status,
        }

    @staticmethod
    def _set_creation_flags(model, pk, fields: set[str]):
        updates: dict[str, Any] = {}
        if "source" in fields:
            updates["source"] = "scrape"
        if "is_approved" in fields:
            updates["is_approved"] = False

        if updates:
            model.objects.filter(pk=pk).update(**updates)

    @staticmethod
    def _normalize_confidence(value) -> float | None:
        try:
            if value is None:
                return None
            numeric = float(value)
            if numeric <= 1.0:
                numeric *= 100.0
            return max(0.0, min(100.0, numeric))
        except (TypeError, ValueError):
            return None

    def _is_significantly_higher_confidence(
        self,
        incoming_confidence: float | None,
        existing_confidence: float | None,
    ) -> bool:
        if incoming_confidence is None:
            return False
        if existing_confidence is None:
            return True
        return incoming_confidence >= (
            existing_confidence + self.STATUS_CONFIDENCE_DELTA
        )

    @staticmethod
    def _append_validation_note(existing: str, note: str) -> str:
        existing = (existing or "").strip()
        note = (note or "").strip()
        if not note:
            return existing
        if not existing:
            return note
        if note in existing:
            return existing
        return f"{existing}\n{note}"
