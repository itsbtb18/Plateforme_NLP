"""Tavily + Groq based news scraper."""

from __future__ import annotations

import logging
import time
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps as django_apps
from django.utils import timezone

from scraping.extractors.news.llm_news_extractor import LLMNewsExtractor
from scraping.network.search_client import TavilySearchClient

from .base import BaseScraper

logger = logging.getLogger(__name__)


class NewsScraper(BaseScraper):
    """Discover Arabic NLP news from web search and LLM extraction."""

    name = "Arabic NLP News (Tavily + Groq)"
    category = "news"
    API_CALL_DELAY_SECONDS = 2

    MODEL_CANDIDATES = (
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

        search_queries = self.get_active_search_queries(self.category)
        if not search_queries:
            logger.warning(
                "No active search queries configured for category '%s'.", self.category
            )
            return

        combined_results: list[dict] = []
        for query in search_queries:
            try:
                time.sleep(self.API_CALL_DELAY_SECONDS)
                results = async_to_sync(search_client.search_web)(query, max_results=12)
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
            candidates = async_to_sync(extractor.extract_news_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("news_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No news candidates extracted from Tavily results.")
            return

        fields = self._model_fields(model)
        author = self._resolve_system_user_if_needed(fields)

        for candidate in candidates:
            if not isinstance(candidate, dict):
                self.items_skipped += 1
                continue

            normalized = self._normalize_candidate(candidate)
            if normalized is None:
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

            try:
                obj, created = model.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
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

            self.results.append(
                {
                    "title": normalized["title_en"],
                    "description": self.truncate(normalized["summary_en"], 400),
                    "type": "news",
                    "url": normalized.get("source_url") or "",
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized.get("source_url") or "",
                    "title_en": normalized["title_en"],
                    "description_en": normalized["summary_en"],
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
                if self._contains_arabic(item["title_ar"] + " " + item["summary_ar"])
                else "en"
            )
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
        if not title_en or not summary_en:
            return None

        title_ar = self._safe_text(item.get("title_ar")) or title_en
        summary_ar = self._safe_text(item.get("summary_ar")) or summary_en

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

        return {
            "title_en": title_en[:300],
            "title_ar": title_ar[:300],
            "summary_en": summary_en[:5000],
            "summary_ar": summary_ar[:5000],
            "source_url": self._safe_text(item.get("source_url"))[:500],
            "published_date": self._safe_text(item.get("published_date"))[:10] or None,
            "tags": tags,
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
