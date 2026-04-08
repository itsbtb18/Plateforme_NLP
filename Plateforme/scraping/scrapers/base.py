"""Core scraper orchestration without legacy HTTP parsing dependencies."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from dateutil import parser as date_parser
from django.contrib.auth import get_user_model
from django.utils import timezone

from scraping.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_NAME, SYSTEM_USER_NAME_AR
from scraping.scrapers.base_dedup import DedupMixin
from scraping.scrapers.base_media import BaseMediaCompat, MediaMixin
from scraping.scrapers.base_text import TextMixin
from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseScraper(TextMixin, MediaMixin, DedupMixin, ABC):
    """Shared run/persistence/dedup orchestration for category scrapers."""

    name: str = "Base Scraper"
    category: str = "unknown"

    def __init__(self):
        self.results: list[dict] = []
        self.errors: list[str] = []
        self.structured_errors: list[dict] = []
        self.items_created: int = 0
        self.items_updated: int = 0
        self.items_skipped: int = 0
        self.validation_stats = {
            "passed": 0,
            "failed_date": 0,
            "failed_fields": 0,
            "failed_freshness": 0,
            "auto_filled": 0,
        }
        self._system_user = None
        self._last_duplicate_match_id = ""

    @abstractmethod
    def scrape(self):
        """Execute category-specific scraping logic."""

    def run(self) -> dict:
        logger.info(
            "scraper_started",
            extra={
                "category": self.category,
                "source_name": self.name,
            },
        )

        self._disable_es_indexing()
        try:
            self.scrape()
        except Exception as exc:
            self._log_error("scraper_crash", str(exc), source=self.name)
            logger.exception("Scraper %s failed", self.name)
        finally:
            self._enable_es_indexing()

        intelligence_summary = self._run_intelligence()

        return {
            "scraper": self.name,
            "category": self.category,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "items_skipped": self.items_skipped,
            "items_found": self.items_created + self.items_updated + self.items_skipped,
            "errors": self.errors,
            "structured_errors": self.structured_errors,
            "results": self.results,
            "intelligence": intelligence_summary,
            "validation_stats": dict(self.validation_stats),
        }

    def get_active_search_queries(self, category: str | None = None) -> list[str]:
        """Return active DB-backed search queries for a scraper category."""
        from scraping.models import SearchQuery

        target_category = (category or self.category or "").strip().lower()
        if not target_category:
            return []

        try:
            queryset = (
                SearchQuery.objects.filter(
                    category=target_category,
                    is_active=True,
                )
                .only("query_text")
                .order_by("id")
            )
        except Exception as exc:
            self._log_error(
                "search_query_lookup_failed",
                str(exc),
                source=self.name,
            )
            return []

        queries: list[str] = []
        for row in queryset:
            query_text = (row.query_text or "").strip()
            if query_text:
                queries.append(query_text)

        return queries

    def _disable_es_indexing(self):
        try:
            from django_elasticsearch_dsl.registries import registry

            self._original_es_update = registry.update
            self._original_es_delete = registry.delete
            registry.update = lambda *a, **kw: None
            registry.delete = lambda *a, **kw: None
        except Exception:
            logger.debug("es_indexing_disable_skipped", exc_info=True)

    def _enable_es_indexing(self):
        try:
            from django_elasticsearch_dsl.registries import registry

            if hasattr(self, "_original_es_update"):
                registry.update = self._original_es_update
            if hasattr(self, "_original_es_delete"):
                registry.delete = self._original_es_delete
        except Exception:
            logger.debug("es_indexing_enable_skipped", exc_info=True)

    def _log_error(
        self,
        error_type: str,
        message: str,
        source: str = "",
        url: str = "",
        extra: dict | None = None,
    ):
        full_message = f"{error_type}: {message}"
        self.errors.append(full_message)

        entry = {
            "type": error_type,
            "message": message,
            "source": source or self.name,
            "url": url,
            "timestamp": timezone.now().isoformat(),
        }
        if extra:
            entry["extra"] = extra

        self.structured_errors.append(entry)
        logger.warning(
            "[%s] %s - %s (source=%s url=%s)",
            self.category,
            error_type,
            message,
            source or self.name,
            url,
        )

    def _notify_skip(self, name: str, url: str, reason: str):
        payload = {
            "name": name,
            "url": url,
            "reason": reason,
            "category": self.category,
            "source_name": self.name,
        }
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        try:
            async_to_sync(channel_layer.group_send)(
                "scraping_status",
                {
                    "type": "item_skipped",
                    **payload,
                },
            )
        except Exception:
            logger.debug("notify_skip_dispatch_failed", exc_info=True)

    def _is_download_enabled(self) -> bool:
        return bool(getattr(SS, "DOWNLOAD_ATTACHMENTS", True))

    def _max_concurrent_downloads(self) -> int:
        value = int(getattr(SS, "MAX_CONCURRENT_DOWNLOADS", 4))
        return max(1, value)

    @staticmethod
    def _coerce_url_list(value) -> list[str]:
        return BaseMediaCompat._coerce_url_list_fallback(value)

    def _collect_page_media_urls(self, page_url: str, category: str) -> dict:
        del page_url
        del category
        return {
            "image_urls": [],
            "pdf_urls": [],
        }

    def _resolve_media_candidates(self, item_data: dict, category: str) -> dict:
        del category
        image_candidates = self._coerce_url_list(
            item_data.get("image_url")
            or item_data.get("thumbnail")
            or item_data.get("banner_image")
        )
        pdf_candidates = self._coerce_url_list(
            item_data.get("pdf_url")
            or item_data.get("file_url")
            or item_data.get("attachment")
        )
        return {
            "image_urls": image_candidates,
            "pdf_urls": pdf_candidates,
        }

    def _download_media(self, item_data: dict, category: str) -> dict:
        del category
        item_data = dict(item_data or {})
        item_data.setdefault("image_local_path", "")
        item_data.setdefault("image_content_file", None)
        item_data.setdefault("pdf_local_path", "")
        item_data.setdefault("pdf_content_file", None)
        return item_data

    def get_system_user(self):
        user_model = get_user_model()

        if self._system_user is not None:
            return self._system_user

        user = user_model.objects.filter(email=SYSTEM_USER_EMAIL).first()
        if user is None:
            try:
                user = user_model.objects.create_user(
                    email=SYSTEM_USER_EMAIL,
                    password=None,
                    full_name=SYSTEM_USER_NAME,
                    full_name_en=SYSTEM_USER_NAME,
                    full_name_ar=SYSTEM_USER_NAME_AR,
                )
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                if hasattr(user, "is_verified"):
                    user.is_verified = True
                if hasattr(user, "is_email_verified"):
                    user.is_email_verified = True
                user.save()
            except Exception:
                user = user_model.objects.filter(is_superuser=True).first()

        if user is None:
            raise RuntimeError(
                "Cannot resolve a system scraper user. Create a superuser first."
            )

        self._system_user = user
        return user

    def get_or_create_country(self, name_en: str, code: str = "", name_ar: str = ""):
        from institutions.models import Country

        normalized_code = (code or name_en[:2]).upper()[:2]
        country, _ = Country.objects.get_or_create(
            code=normalized_code,
            defaults={
                "name_en": name_en,
                "name_ar": name_ar or name_en,
            },
        )
        return country

    def get_or_create_institution(self, name: str, **kwargs):
        from institutions.models import Institution

        normalized_name = (name or "").strip()
        if not normalized_name:
            return None

        existing = Institution.objects.filter(name_en__iexact=normalized_name).first()
        if existing is not None:
            return existing

        country = kwargs.get("country") or self.get_or_create_country(
            "International", "XX"
        )
        city = (kwargs.get("city") or "").strip()
        website = (kwargs.get("website") or "").strip()
        description = kwargs.get("description") or (
            f"{normalized_name} is a research institution active in natural "
            "language processing and computational linguistics."
        )
        country_name = getattr(country, "name_en", "")
        address = f"{city}, {country_name}" if city else country_name

        try:
            return Institution.objects.create(
                name=normalized_name,
                name_en=normalized_name,
                name_ar=(kwargs.get("name_ar") or normalized_name)[:255],
                acronym=(kwargs.get("acronym") or "")[:50],
                type=(kwargs.get("inst_type") or "University")[:50],
                country=country,
                city_en=city,
                city=city,
                city_ar=city,
                website=website,
                email=(kwargs.get("email") or "")[:254],
                phone=(kwargs.get("phone") or "")[:50],
                address=address,
                address_en=address,
                address_ar=address,
                description=description,
                description_en=description,
                description_ar=description,
                created_by=self.get_system_user(),
            )
        except Exception as exc:
            self._log_error(
                "institution_create",
                str(exc),
                source=normalized_name,
                url=website,
            )
            return None

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip().lower()

    @staticmethod
    def _normalize_url(value: str, strip_www: bool = False) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""

        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()
        if strip_www and netloc.startswith("www."):
            netloc = netloc[4:]
        path = (parsed.path or "").rstrip("/")
        return f"{scheme}://{netloc}{path}"

    @staticmethod
    def _title_similarity(left: str, right: str) -> float:
        return SequenceMatcher(
            None,
            BaseScraper._normalize_text(left),
            BaseScraper._normalize_text(right),
        ).ratio()

    @staticmethod
    def _extract_instructor(value: str) -> str:
        text = value or ""
        match = re.search(r"(?:instructor|teacher)\s*[:\-]\s*([^\n\r]+)", text, re.I)
        if match is None:
            return ""
        return BaseScraper._normalize_text(match.group(1))

    @staticmethod
    def _item_display_name(item_data: dict) -> str:
        for key in ("title_en", "title", "name_en", "name"):
            value = (item_data.get(key) or "").strip()
            if value:
                return value
        return "untitled"

    def _set_duplicate_match(self, existing_obj):
        self._last_duplicate_match_id = str(getattr(existing_obj, "id", ""))

    def _record_duplicate_skip(
        self, category: str, item_data: dict, reason: str, match_score: float = 0.0
    ):
        item_label = self._item_display_name(item_data)
        matched_id = getattr(self, "_last_duplicate_match_id", "")
        reason_code = self._normalize_skip_reason(reason)
        logger.info(
            "item_skipped",
            extra={
                "category": category,
                "source_name": self.name,
                "item_title": item_label,
                "item_id": matched_id or "unknown",
                "skip_reason": reason_code,
            },
        )

        try:
            from scraping.models import ScrapedItemMeta

            ScrapedItemMeta.objects.update_or_create(
                category=category,
                item_title=item_label[:300],
                defaults={
                    "item_id": matched_id,
                    "skip_reason": reason_code,
                    "source_name": item_data.get("source_name") or self.name,
                    "source_url": item_data.get("source_url") or "",
                    "match_score": match_score,
                    "matched_item_id": matched_id or None,
                    "was_skipped": True,
                },
            )
        except Exception as exc:
            self._log_error("dedup_skip_meta", str(exc), source=item_label)

    @staticmethod
    def _normalize_skip_reason(reason: str) -> str:
        lowered = BaseScraper._normalize_text(reason or "")
        if "url" in lowered or "website" in lowered or "link" in lowered:
            return "dedup_url"
        if "name" in lowered or "title" in lowered or "exact" in lowered:
            return "dedup_name"
        return "dedup_similarity"

    @staticmethod
    def _recent_dedup_queryset(queryset):
        field_names = {field.name for field in queryset.model._meta.fields}
        order_field = "-created_at" if "created_at" in field_names else "-id"
        return queryset.order_by(order_field)[: int(getattr(SS, "DEDUP_WINDOW", 300))]

    def _dedup_event(self, item_data: dict) -> tuple[bool, str, float]:
        from events.models import Event

        website_url = (
            item_data.get("website_url") or item_data.get("website") or ""
        ).strip()
        if website_url:
            existing = Event.objects.filter(website__iexact=website_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "event website exact match", 1.0

        candidate_title = item_data.get("title_en") or item_data.get("title") or ""
        if candidate_title:
            recent_events = self._recent_dedup_queryset(
                Event.objects.only("id", "title", "title_en")
            )
            threshold = float(getattr(SS, "JACCARD_THRESHOLD", 0.85))
            for event in recent_events:
                existing_title = event.title_en or event.title
                similarity = self._title_similarity(candidate_title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(event)
                    return True, "event title similarity", similarity

        return False, "", 0.0

    def _dedup_tool(self, item_data: dict) -> tuple[bool, str, float]:
        from resources.models import NLPTool

        github_url = (item_data.get("github_url") or "").strip()
        if github_url:
            existing = NLPTool.objects.filter(github_url__iexact=github_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool github exact match", 1.0

        access_link = (item_data.get("access_link") or "").strip()
        if access_link:
            existing = NLPTool.objects.filter(access_link__iexact=access_link).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool access_link exact match", 1.0

        title = item_data.get("title_en") or item_data.get("title") or ""
        if title:
            recent_tools = self._recent_dedup_queryset(
                NLPTool.objects.only("id", "title", "title_en")
            )
            threshold = float(getattr(SS, "STRICT_JACCARD", 0.9))
            for tool in recent_tools:
                existing_title = tool.title_en or tool.title
                similarity = self._title_similarity(title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(tool)
                    return True, "tool title similarity", similarity

        return False, "", 0.0

    def _dedup_news(self, item_data: dict) -> tuple[bool, str, float]:
        del item_data
        return False, "", 0.0

    def _dedup_course(self, item_data: dict) -> tuple[bool, str, float]:
        from resources.models import Course

        access_link = (
            item_data.get("course_url") or item_data.get("access_link") or ""
        ).strip()
        if access_link:
            existing = Course.objects.filter(access_link__iexact=access_link).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "course access_link exact match", 1.0

        title = item_data.get("title_en") or item_data.get("title") or ""
        if title:
            recent_courses = self._recent_dedup_queryset(
                Course.objects.only("id", "title", "title_en")
            )
            threshold = float(getattr(SS, "STRICT_JACCARD", 0.9))
            for course in recent_courses:
                existing_title = course.title_en or course.title
                similarity = self._title_similarity(title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(course)
                    return True, "course title similarity", similarity

        return False, "", 0.0

    def _dedup_institution(self, item_data: dict) -> tuple[bool, str, float]:
        del item_data
        return False, "", 0.0

    def _check_duplicate_policy(self, category, item_data) -> tuple[bool, str, float]:
        checker_map = {
            "events": self._dedup_event,
            "tools": self._dedup_tool,
            "courses": self._dedup_course,
            "news": self._dedup_news,
            "institutions": self._dedup_institution,
        }
        checker = checker_map.get((category or "").strip().lower())
        if checker is None:
            return False, "", 0.0

        is_duplicate, reason, score = checker(item_data)
        if is_duplicate:
            self._record_duplicate_skip(category, item_data, reason, match_score=score)
        return is_duplicate, reason, score

    def is_duplicate(self, title, category, model_class):
        del model_class
        payload = {
            "title": title,
            "title_en": title,
        }
        is_duplicate, _, _ = self._check_duplicate_policy(category, payload)
        return is_duplicate

    @staticmethod
    def parse_date(
        date_str: str | None,
        default: datetime | None = None,
    ) -> datetime | None:
        if not date_str:
            return default
        try:
            parsed = date_parser.parse(date_str, fuzzy=True)
            if isinstance(parsed, datetime):
                return parsed
            return datetime.combine(parsed, datetime.min.time())
        except (ValueError, OverflowError, TypeError):
            return default

    @staticmethod
    def truncate(text: str, max_len: int = 200) -> str:
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        cleaned = re.sub(r"\s+", " ", text).strip()
        if self.detect_arabic_ratio(cleaned) > 0.1:
            cleaned = self.normalize_arabic_text(cleaned)
        return cleaned

    def normalize_arabic_text(self, text):
        if not text or not text.strip():
            return text
        try:
            import pyarabic.araby as araby

            normalized = araby.strip_tashkeel(text)
            normalized = araby.normalize_alef(normalized)
            normalized = araby.normalize_lamalef(normalized)
            return normalized.strip()
        except Exception:
            normalized = re.sub(r"[\u0617-\u061A\u064B-\u065F]", "", text)
            normalized = re.sub(r"[أإآ]", "ا", normalized)
            normalized = re.sub(r"ة", "ه", normalized)
            return normalized.strip()

    def detect_arabic_ratio(self, text):
        if not text or not text.strip():
            return 0.0
        arabic_chars = len(
            re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text)
        )
        alpha_chars = len(re.findall(r"[^\W\d_]", text))
        if alpha_chars == 0:
            return 0.0
        return arabic_chars / alpha_chars

    def detect_language(self, text: str) -> str:
        if not text or len(text.strip()) < 20:
            return "unknown"

        if self.detect_arabic_ratio(text) >= 0.30:
            return "ar"

        try:
            from langdetect import DetectorFactory, detect

            DetectorFactory.seed = 0
            detected = detect(text)
            if detected in {"ar", "fr", "en"}:
                return detected
            return "unknown"
        except Exception:
            return "unknown"

    def is_relevant_language(self, text):
        language = self.detect_language(text)
        return language in {"ar", "fr", "en"}

    def _run_intelligence(self) -> dict:
        try:
            from scraping.field_mapping import calculate_completeness_score
            from scraping.intelligence import (
                classify_domain,
                classify_domain_primary,
                compute_relevance_score,
            )
            from scraping.models import ScrapedItemMeta
        except Exception as exc:
            return {
                "status": "skipped",
                "reason": str(exc),
            }

        scored = 0
        domain_counts: dict[str, int] = {}
        avg_score = 0.0

        for item in self.results:
            title = item.get("title", "")
            if not title:
                continue

            text = f"{title} {item.get('description', '')} {item.get('type', '')}"
            domain_scores = classify_domain(text)
            primary_domain = classify_domain_primary(text)
            score = compute_relevance_score(
                text=text,
                has_description=bool(item.get("description") or item.get("type")),
                has_website=bool(item.get("url")),
                has_arabic=any("\u0600" <= c <= "\u06ff" for c in text),
                domain_scores=domain_scores,
            )

            completeness = calculate_completeness_score(item, self.category)
            defaults = {
                "domain_scores": domain_scores,
                "primary_domain": primary_domain,
                "relevance_score": score,
                "completeness_score": completeness,
                "source_name": item.get("source_name") or self.name,
                "source_url": item.get("source_url") or item.get("url") or "",
                "was_skipped": False,
                "enrichment_status": "not_enriched",
            }

            try:
                ScrapedItemMeta.objects.update_or_create(
                    category=self.category,
                    item_title=(item.get("title_en") or title)[:300],
                    defaults=defaults,
                )
            except Exception:
                logger.debug("intelligence_meta_update_failed", exc_info=True)

            scored += 1
            avg_score += score
            domain_counts[primary_domain] = domain_counts.get(primary_domain, 0) + 1

        return {
            "status": "completed",
            "items_scored": scored,
            "avg_relevance_score": round(avg_score / max(scored, 1), 1),
            "domain_distribution": domain_counts,
        }
