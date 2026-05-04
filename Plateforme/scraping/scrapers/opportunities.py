"""Tavily + Groq based opportunities scraper."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps as django_apps
from django.db import transaction
from django.utils import timezone

from scraping.extractors.opportunities.llm_opportunity_extractor import (
    LLMOpportunityExtractor,
)
from scraping.field_mapping import get_auto_translate_fields
from scraping.network.search_client import TavilySearchClient
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

from .base import BaseScraper

logger = logging.getLogger(__name__)


class OpportunityScraper(BaseScraper):
    """Discover NLP opportunities from web search and LLM extraction."""

    name = "NLP Opportunities (Tavily + Groq)"
    category = "opportunities"
    API_CALL_DELAY_SECONDS = 2
    STATUS_CONFIDENCE_DELTA = 15.0

    MODEL_CANDIDATES = (
        ("pages", "Opportunity"),
        ("events", "Opportunity"),
        ("resources", "Opportunity"),
    )

    def scrape(self):
        model = self._resolve_model()
        if model is None:
            self._log_error(
                "opportunity_model_missing",
                "No Opportunity model found in configured model candidates",
                source=self.name,
            )
            return

        try:
            search_client = TavilySearchClient()
            extractor = LLMOpportunityExtractor()
        except Exception as exc:
            self._log_error("opportunity_init_failed", str(exc), source=self.name)
            logger.warning("Opportunity scraper initialization failed: %s", exc)
            return

        if not search_client.is_enabled:
            self._log_error(
                "opportunity_search_unavailable",
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
                results = async_to_sync(search_client.search_opportunities)(query)
            except Exception as exc:
                self._log_error(
                    "opportunity_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                combined_results.extend(results)

        if not combined_results:
            logger.warning("No opportunity search results returned by Tavily.")
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
            candidates = async_to_sync(extractor.extract_opportunities_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error(
                "opportunity_llm_extraction_failed",
                str(exc),
                source=self.name,
            )
            return

        if not candidates:
            logger.warning("No opportunity candidates extracted from Tavily results.")
            return

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            "job_title_ar",
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
                        candidate.get("job_title")
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
                    "opportunity_lookup_unavailable",
                    "No compatible unique lookup field found for model",
                    source=self.name,
                    url=normalized.get("url") or "",
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
                            normalized["job_title"],
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
                    "opportunity_upsert_failed",
                    str(exc),
                    source=normalized["job_title"],
                    url=normalized.get("url") or "",
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
                    "title": normalized["job_title"],
                    "description": self.truncate(normalized["description"], 400),
                    "type": normalized["opportunity_type"],
                    "url": normalized.get("url") or "",
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized.get("url") or "",
                    "title_en": normalized["job_title"],
                    "title_ar": normalized.get("title_ar"),
                    "description_en": normalized["description"],
                    "description_ar": normalized.get("description_ar"),
                    "job_title": normalized["job_title"],
                    "opportunity_type": normalized["opportunity_type"],
                    "deadline": normalized.get("deadline"),
                    "institution_name": normalized["institution_name"],
                    "translation_status": normalized.get(
                        "translation_status", "pending"
                    ),
<<<<<<< HEAD
                    "relevance_score": normalized.get("relevance_score"),
                    "extraction_confidence": normalized.get("extraction_confidence"),
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                logger.warning(
                    "System user unavailable for opportunity scraper: %s", exc
                )
        return None

    def _build_lookup(self, fields: set[str], item: dict[str, Any]):
        source_url = item.get("url")
        if source_url:
            for candidate in ("url", "source_url", "access_link", "application_url"):
                if candidate in fields:
                    return {candidate: source_url}

        for candidate in ("job_title", "title_en", "title", "name"):
            if candidate in fields:
                return {candidate: item["job_title"]}

        return None

    def _build_defaults(
        self,
        fields: set[str],
        item: dict[str, Any],
        author,
    ) -> dict[str, Any]:
        defaults: dict[str, Any] = {}

        self._set_if_present(defaults, fields, "job_title", item["job_title"])
        self._set_if_present(defaults, fields, "title", item["job_title"])
        self._set_if_present(defaults, fields, "title_en", item["job_title"])
        self._set_if_present(defaults, fields, "title_ar", item.get("title_ar"))
        self._set_if_present(defaults, fields, "description", item["description"])
        self._set_if_present(defaults, fields, "description_en", item["description"])
        self._set_if_present(
            defaults,
            fields,
            "description_ar",
            item.get("description_ar"),
        )
        self._set_if_present(
            defaults, fields, "institution_name", item["institution_name"]
        )
        self._set_if_present(
            defaults, fields, "opportunity_type", item["opportunity_type"]
        )
        self._set_if_present(defaults, fields, "location", item["location"])

        if item.get("deadline"):
            self._set_if_present(defaults, fields, "deadline", item["deadline"])
            self._set_if_present(defaults, fields, "end_date", item["deadline"])
            self._set_if_present(defaults, fields, "closing_date", item["deadline"])

        if item.get("url"):
            self._set_if_present(defaults, fields, "url", item["url"])
            self._set_if_present(defaults, fields, "source_url", item["url"])
            self._set_if_present(defaults, fields, "access_link", item["url"])
            self._set_if_present(defaults, fields, "application_url", item["url"])

        if "keywords" in fields:
            defaults["keywords"] = ", ".join(
                [
                    "nlp",
                    "ai",
                    item["opportunity_type"].lower(),
                    item["institution_name"].lower(),
                ]
            )
        if "entities" in fields:
            defaults["entities"] = {
                "institution_name": item["institution_name"],
                "opportunity_type": item["opportunity_type"],
                "deadline": item.get("deadline"),
                "location": item["location"],
            }
        if "source_name" in fields:
            defaults["source_name"] = "Tavily Search + Groq"
        if "language" in fields:
            defaults["language"] = "en"
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
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    def _normalize_candidate(self, item: dict[str, Any]) -> dict[str, Any] | None:
        job_title = self._safe_text(item.get("job_title"))
        institution_name = self._safe_text(item.get("institution_name"))
        description = self._safe_text(item.get("description"))

        if not job_title or not institution_name:
            return None
        if not description:
            description = "[NEEDS RESEARCH]"

        translation_status = infer_translation_status(
            raw_status=self._safe_text(item.get("translation_status")) or "pending",
            english_values=[job_title, description],
            arabic_values=[item.get("title_ar"), item.get("description_ar")],
        )

        return {
            "job_title": job_title[:300],
            "title_ar": self._safe_text(item.get("title_ar"))[:300] or None,
            "description_ar": self._safe_text(item.get("description_ar"))[:5000]
            or None,
            "institution_name": institution_name[:255],
            "opportunity_type": self._normalize_type(item.get("opportunity_type")),
            "deadline": self._normalize_date(item.get("deadline")),
            "location": self._safe_text(item.get("location"))[:255] or "Online",
            "url": (
                self._safe_text(item.get("url"))
                or self._safe_text(item.get("source_url"))
                or self._safe_text(item.get("access_link"))
                or self._safe_text(item.get("application_url"))
                or "[NEEDS RESEARCH]"
            )[:500],
            "description": description[:5000],
            "confidence_score": self._normalize_confidence(
                item.get("confidence_score", item.get("extraction_confidence"))
            ),
            "translation_status": translation_status,
<<<<<<< HEAD
            "relevance_score": item.get("relevance_score"),
            "extraction_confidence": item.get("extraction_confidence"),
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }

    def _normalize_type(self, value: Any) -> str:
        text = self._safe_text(value).lower()
        if text in {"phd", "ph.d", "doctorate"}:
            return "Phd"
        if text in {"postdoc", "post-doc", "postdoctoral", "post doc"}:
            return "PostDoc"
        if text in {"grant", "funding", "fellowship", "scholarship"}:
            return "Grant"
        return "Job"

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if not text or text == "[NEEDS RESEARCH]" or text.lower() == "null":
            return None
            
        candidate = text[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
            return candidate
        return None

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

    @staticmethod
    def _set_creation_flags(model, pk, fields: set[str]):
        updates: dict[str, Any] = {}
        if "source" in fields:
            updates["source"] = "scrape"
        if "is_approved" in fields:
            updates["is_approved"] = False

        if updates:
            model.objects.filter(pk=pk).update(**updates)
