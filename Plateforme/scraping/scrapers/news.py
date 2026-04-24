"""Tavily + Groq based news scraper."""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from feed.models import Post
from scraping.extractors.news.llm_news_extractor import LLMNewsExtractor
from scraping.network.search_client import TavilySearchClient
from scraping.utils import infer_translation_status

from .base import BaseScraper

logger = logging.getLogger(__name__)


class NewsScraper(BaseScraper):
    """Discover Arabic NLP news/papers from web search and LLM extraction."""

    name = "Arabic NLP News (Tavily + Groq)"
    category = "news"
    API_CALL_DELAY_SECONDS = 2
    STATUS_CONFIDENCE_DELTA = 15.0

    def scrape(self):
        from feed.models import Post

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

        author = self.get_system_user()

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
                    str(candidate.get("title_en") or candidate.get("title") or "").strip()
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

            lookup = {"title_en": normalized["title_en"]}
            model_fields = {f.name for f in Post._meta.get_fields()}
            defaults = self._build_defaults(model_fields, normalized, author)

            try:
                with transaction.atomic():
                    news_obj = Post.objects.select_for_update().filter(**lookup).first()
                    if news_obj is not None:
                        is_terminal = self._is_approved_record(news_obj)
                        has_higher_confidence = self._is_significantly_higher_confidence(
                            incoming_confidence=defaults.get("confidence_score"),
                            existing_confidence=getattr(news_obj, "confidence_score", None),
                        )

                        if is_terminal and not has_higher_confidence:
                            # Limited update (metadata only)
                            limited_fields = {"last_scraped_at", "update_counter"}
                            for f in limited_fields:
                                if f in model_fields:
                                    setattr(news_obj, f, defaults.get(f, getattr(news_obj, f)))
                        else:
                            # Full update or standard update
                            for field_name, field_value in defaults.items():
                                setattr(news_obj, field_name, field_value)

                        news_obj.save()
                        created = False
                    else:
                        news_obj = Post.objects.create(**defaults)
                        created = True

                    self._set_creation_flags(Post, news_obj.pk, model_fields)

            except Exception as exc:
                self._log_error(
                    "news_upsert_failed",
                    str(exc),
                    source=normalized["title_en"],
                    url=normalized["source_url"],
                )
                self.items_skipped += 1
                continue

            if created:
                self.items_created += 1
            else:
                self.items_updated += 1

            self._track_saved_item_status(normalized)

            self.results.append(
                {
                    "title": normalized["title_en"],
                    "description": self.truncate(normalized["summary_en"], 400),
                    "url": normalized["source_url"],
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized["source_url"],
                    "source_domain": (
                        urlparse(normalized["source_url"]).netloc or ""
                    ).lower(),
                    "title_en": normalized["title_en"],
                    "title_ar": normalized["title_ar"],
                    "published_date": normalized["published_date"],
                    "confidence_score": normalized["confidence_score"],
                    "translation_status": normalized.get(
                        "translation_status", "pending"
                    ),
                    "relevance_score": normalized.get("relevance_score"),
                    "extraction_confidence": normalized.get("extraction_confidence"),
                }
            )

    def _get_lookup(self, fields: set[str], item: dict[str, Any]) -> dict[str, Any] | None:
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

        normalized_published_date = self._normalize_date_text(
            item.get("published_date")
        )
        if normalized_published_date:
            self._set_if_present(
                defaults,
                fields,
                "published_date",
                normalized_published_date,
            )
            self._set_if_present(defaults, fields, "date", normalized_published_date)

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

    @classmethod
    def _normalize_date_text(cls, value: Any) -> str | None:
        text = cls._safe_text(value)
        if not text or text == "[NEEDS RESEARCH]":
            return None

        candidate = text[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
            return candidate
        return None

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
            "published_date": self._normalize_date_text(item.get("published_date")),
            "tags": tags,
            "confidence_score": self._normalize_confidence(
                item.get("confidence_score", item.get("extraction_confidence"))
            ),
            "translation_status": translation_status,
            "relevance_score": item.get("relevance_score"),
            "extraction_confidence": item.get("extraction_confidence"),
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
