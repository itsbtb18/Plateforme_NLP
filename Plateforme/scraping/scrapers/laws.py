"""Tavily-based laws scraper for Arabic NLP legal and policy content."""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.db import transaction
from django.utils import timezone

from scraping.network.search_client import TavilySearchClient

from .base import BaseScraper

logger = logging.getLogger(__name__)


class LawScraper(BaseScraper):
    """Discover legal framework and AI policy documents from the web."""

    name = "Arabic NLP Laws (Tavily)"
    category = "laws"
    API_CALL_DELAY_SECONDS = 1

    DEFAULT_SEARCH_QUERIES = (
        "Arabic NLP legal framework",
        "AI research regulations MENA",
    )

    MODEL_CANDIDATES = (("resources", "Law"),)

    def scrape(self):
        model = self._resolve_model()
        if model is None:
            self._log_error(
                "laws_model_missing",
                "No Law model found in configured model candidates",
                source=self.name,
            )
            return

        try:
            search_client = TavilySearchClient()
        except Exception as exc:
            self._log_error("laws_init_failed", str(exc), source=self.name)
            logger.warning("Law scraper initialization failed: %s", exc)
            return

        if not search_client.is_enabled:
            self._log_error(
                "laws_search_unavailable",
                search_client.disabled_reason or "Tavily search client unavailable",
                source=self.name,
            )
            return

        search_queries = self.get_active_search_queries(self.category) or list(
            self.DEFAULT_SEARCH_QUERIES
        )
        if not search_queries:
            logger.warning("No active or default search queries configured for laws.")
            return

        combined_results: list[dict] = []
        seen_urls: set[str] = set()
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
                results = async_to_sync(search_client.search_laws)(query)
            except Exception as exc:
                self._log_error(
                    "laws_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            for result in results or []:
                if not isinstance(result, dict):
                    continue
                result_url = self._safe_text(result.get("url"))
                if not result_url or result_url in seen_urls:
                    continue
                result_title = self._safe_text(result.get("title"))
                result_content = self._safe_text(result.get("content"))
                if not result_title and not result_content:
                    continue
                seen_urls.add(result_url)
                combined_results.append(
                    {
                        "title": result_title,
                        "url": result_url,
                        "content": result_content,
                        "score": result.get("score"),
                    }
                )

        if not combined_results:
            logger.warning("No law search results returned by Tavily.")
            return

        candidates: list[dict] = []
        total_candidates = len(combined_results)
        self.emit_progress(
            "validation",
            0,
            total_candidates,
            "✅ Starting validation...",
        )

        for candidate_index, row in enumerate(combined_results, start=1):
            self.emit_progress(
                "saving",
                candidate_index,
                total_candidates,
                f"💾 Saving item {candidate_index}/{total_candidates}",
                current_item=str(row.get("title") or row.get("url") or ""),
            )

            normalized = self._normalize_candidate(row)
            if normalized is None:
                self.items_skipped += 1
                continue

            if not self.passes_min_confidence_to_save(normalized):
                self.items_skipped += 1
                continue

            lookup = (
                {"source_url": normalized["source_url"]}
                if normalized.get("source_url")
                and normalized["source_url"] != "[NEEDS RESEARCH]"
                else {"law_title": normalized["law_title"]}
            )

            defaults = self._build_defaults(normalized)
            now = timezone.now()

            try:
                with transaction.atomic():
                    law = model.objects.select_for_update().filter(**lookup).first()
                    if law is None and normalized["law_title"]:
                        semantic_queryset = self._recent_dedup_queryset(
                            model.objects.only("id", "law_title")
                        )
                        semantic_law, semantic_score = self._find_semantic_title_match(
                            semantic_queryset,
                            normalized["law_title"],
                            title_fields=("law_title",),
                        )
                        if semantic_law is not None:
                            law = semantic_law

                    if law is not None:
                        defaults["last_scraped_at"] = now
                        defaults["update_counter"] = int(law.update_counter or 0) + 1
                        existing_status = str(
                            getattr(law, "scrape_status", "") or ""
                        ).upper()
                        if self._is_terminal_review_status(existing_status):
                            defaults = self._build_terminal_status_update_defaults(
                                existing_obj=law,
                                incoming_defaults=defaults,
                                metadata_fields={
                                    "last_scraped_at",
                                    "update_counter",
                                    "updated_at",
                                },
                            )
                        for field_name, field_value in defaults.items():
                            setattr(law, field_name, field_value)
                        law.save()
                        created = False
                    else:
                        defaults["last_scraped_at"] = now
                        defaults.setdefault("update_counter", 0)
                        law = model.objects.create(**{**lookup, **defaults})
                        created = True
            except Exception as exc:
                self._log_error(
                    "law_upsert_failed",
                    str(exc),
                    source=normalized["law_title"],
                    url=normalized.get("source_url") or "",
                )
                self.items_skipped += 1
                continue

            if created:
                self.items_created += 1
            else:
                self.items_updated += 1
            self._track_saved_item_status(defaults)

            candidates.append(
                {
                    "law_title": normalized["law_title"],
                    "authority": normalized["authority"],
                    "publication_date": normalized.get("publication_date"),
                    "source_url": normalized["source_url"],
                }
            )

        self.results.extend(candidates)

    def _resolve_model(self):
        from django.apps import apps as django_apps

        for app_label, model_name in self.MODEL_CANDIDATES:
            try:
                model = django_apps.get_model(app_label, model_name)
            except LookupError:
                continue
            if model is not None:
                return model
        return None

    def _build_defaults(self, item: dict) -> dict:
        return {
            "law_title": item["law_title"],
            "authority": item["authority"],
            "publication_date": item.get("publication_date"),
            "legal_text": item["legal_text"],
            "category_tags": item.get("category_tags") or [],
            "source_url": item["source_url"],
            "source_name": "Tavily Search",
            "confidence_score": item.get("confidence_score"),
            "scrape_status": item.get("scrape_status") or "PENDING_REVIEW",
            "approval_status": item.get("approval_status") or "pending",
            "validation_notes": item.get("validation_notes") or "",
            "is_approved": False,
            "created_by": self.get_system_user(),
        }

    def _normalize_candidate(self, item: dict) -> dict | None:
        law_title = self._safe_text(item.get("law_title") or item.get("title"))
        if not law_title:
            return None

        source_url = self._safe_text(item.get("url") or item.get("source_url"))
        if not source_url:
            source_url = "[NEEDS RESEARCH]"

        content = self._safe_text(item.get("content"))
        if not content:
            content = "[NEEDS RESEARCH]"

        authority = self._safe_text(item.get("authority"))
        if not authority:
            authority = self._authority_from_url(source_url)

        publication_date = self._parse_publication_date(f"{law_title}\n{content}")

        category_tags = self._extract_category_tags(law_title, content, source_url)
        translation_status = "pending"
        if self._contains_arabic(f"{law_title} {authority} {content}"):
            translation_status = "translated"

        normalized = {
            "law_title": law_title[:300],
            "title": law_title[:300],
            "title_en": law_title[:300],
            "description": content[:5000],
            "description_en": content[:5000],
            "authority": (authority or "[NEEDS RESEARCH]")[:255],
            "publication_date": publication_date,
            "published_date": publication_date.isoformat()
            if publication_date
            else None,
            "legal_text": content[:5000],
            "category_tags": category_tags,
            "source_url": source_url[:500],
            "url": source_url[:500],
            "confidence_score": self._normalize_confidence(item.get("score")),
            "scrape_status": "PENDING_REVIEW",
            "approval_status": "pending",
            "validation_notes": "",
            "translation_status": translation_status,
        }
        return normalized

    @staticmethod
    def _safe_text(value) -> str:
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

    def _authority_from_url(self, source_url: str) -> str:
        if not source_url or source_url == "[NEEDS RESEARCH]":
            return "[NEEDS RESEARCH]"
        parsed = urlparse(source_url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        if not host:
            return "[NEEDS RESEARCH]"
        return host.split(".")[0].replace("-", " ").title()

    def _parse_publication_date(self, text: str):
        normalized = self._safe_text(text)
        if not normalized:
            return None

        iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", normalized)
        if iso_match:
            try:
                return date(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3)),
                )
            except ValueError:
                return None

        year_match = re.search(r"\b(20\d{2})\b", normalized)
        if year_match:
            try:
                return date(int(year_match.group(1)), 1, 1)
            except ValueError:
                return None

        return None

    def _extract_category_tags(
        self, law_title: str, content: str, source_url: str
    ) -> list[str]:
        blob = f"{law_title} {content} {source_url}".lower()
        tags = ["laws", "legal-framework"]
        if "ai" in blob or "artificial intelligence" in blob:
            tags.append("ai-policy")
        if "regulation" in blob or "regulations" in blob:
            tags.append("regulation")
        if "framework" in blob:
            tags.append("framework")
        if "arabic" in blob:
            tags.append("arabic-nlp")
        if "mena" in blob or "middle east" in blob:
            tags.append("mena")
        return sorted(set(tags))
