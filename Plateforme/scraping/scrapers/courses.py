"""Tavily + Groq based courses scraper."""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from django.db import transaction
from django.utils import timezone

from scraping.extractors.courses.llm_course_extractor import LLMCourseExtractor
from scraping.field_mapping import get_auto_translate_fields
from scraping.network.search_client import TavilySearchClient
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

from .base import BaseScraper

logger = logging.getLogger(__name__)


class CourseScraper(BaseScraper):
    """Discover NLP/AI courses from web search and LLM extraction."""

    name = "NLP/AI Courses (Tavily + Groq)"
    category = "courses"
    API_CALL_DELAY_SECONDS = 2

    LEVEL_MAP = {
        "beginner": "bachelor",
        "intro": "bachelor",
        "basic": "bachelor",
        "intermediate": "master",
        "advanced": "doctorate",
        "expert": "doctorate",
    }

    PLATFORM_MAP = {
        "coursera": "coursera",
        "youtube": "youtube",
        "mit": "mit",
        "edx": "edx",
        "university": "university",
    }

    def scrape(self):
        from resources.models import Course

        try:
            search_client = TavilySearchClient()
            extractor = LLMCourseExtractor()
        except Exception as exc:
            self._log_error("courses_init_failed", str(exc), source=self.name)
            logger.warning("Course scraper initialization failed: %s", exc)
            return

        if not search_client.is_enabled:
            self._log_error(
                "courses_search_unavailable",
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
                results = async_to_sync(search_client.search_courses)(query)
            except Exception as exc:
                self._log_error(
                    "courses_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                combined_results.extend(results)

        if not combined_results:
            logger.warning("No course search results returned by Tavily.")
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
            candidates = async_to_sync(extractor.extract_courses_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("courses_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No course candidates extracted from Tavily results.")
            return

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            *get_auto_translate_fields(self.category),
        ]
        candidates = translator.batch_translate(candidates, fields=fields_to_translate)

        author = self.get_system_user()
        academic_year = self._default_academic_year()

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

            institution = self._resolve_institution(normalized["platform_name"])
            if institution is None:
                self.items_skipped += 1
                continue

            lookup = (
                {"access_link": normalized["url"]}
                if normalized["url"]
                else {"title_en": normalized["title_en"]}
            )

            defaults = {
                "title": normalized["title_en"],
                "title_ar": normalized["title_ar"] or "",
                "description": normalized["description_en"],
                "description_en": normalized["description_en"],
                "description_ar": normalized["description_ar"] or "",
                "author": author,
                "field": "nlp",
                "academic_level": normalized["academic_level"],
                "teacher": author,
                "institution": institution,
                "academic_year": academic_year,
                "prerequisites": "",
                "syllabus": "",
                "instructor": normalized["platform_name"],
                "duration": "",
                "platform": normalized["platform"],
                "enrollment_url": normalized["url"],
                "is_free": normalized["is_free"],
                "price": normalized["price_decimal"],
                "source_url": normalized["url"],
                "source_name": "Tavily Search + Groq",
                "access_link": normalized["url"],
                "keywords": normalized["keywords"],
                "entities": {
                    "platform": normalized["platform_name"],
                    "level": normalized["raw_level"],
                    "price": normalized["raw_price"],
                },
                "language": normalized["language"],
                "approval_status": str(
                    normalized.get("approval_status") or "pending"
                ).lower(),
                "is_approved": False,
                "update_date": timezone.now(),
            }

            try:
                now = timezone.now()
                with transaction.atomic():
                    course = Course.objects.select_for_update().filter(**lookup).first()
                    if course is not None:
                        defaults["last_scraped_at"] = now
                        defaults["update_counter"] = (
                            int(getattr(course, "update_counter", 0) or 0) + 1
                        )
                        if self._is_approved_record(course):
                            defaults = self._build_terminal_status_update_defaults(
                                existing_obj=course,
                                incoming_defaults=defaults,
                                metadata_fields={"last_scraped_at", "update_counter"},
                            )
                        for field_name, field_value in defaults.items():
                            setattr(course, field_name, field_value)
                        course.save()
                        created = False
                    else:
                        semantic_queryset = self._recent_dedup_queryset(
                            Course.objects.only("id", "title", "title_en")
                        )
                        semantic_course, semantic_score = self._find_semantic_title_match(
                            semantic_queryset,
                            normalized["title_en"],
                            title_fields=("title_en", "title"),
                        )
                        if semantic_course is not None:
                            course = semantic_course
                            defaults["last_scraped_at"] = now
                            defaults["update_counter"] = (
                                int(getattr(course, "update_counter", 0) or 0) + 1
                            )
                            if self._is_approved_record(course):
                                defaults = self._build_terminal_status_update_defaults(
                                    existing_obj=course,
                                    incoming_defaults=defaults,
                                    metadata_fields={"last_scraped_at", "update_counter"},
                                )
                            for field_name, field_value in defaults.items():
                                setattr(course, field_name, field_value)
                            course.save()
                            created = False
                        else:
                            defaults["last_scraped_at"] = now
                            defaults.setdefault("update_counter", 0)
                            create_data = dict(defaults)
                            create_data.update(lookup)
                            course = Course.objects.create(**create_data)
                            created = True
            except Exception as exc:
                self._log_error(
                    "course_upsert_failed",
                    str(exc),
                    source=normalized["title_en"],
                    url=normalized["url"],
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
                    "description": self.truncate(normalized["description_en"], 400),
                    "type": "course",
                    "url": normalized["url"],
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized["url"],
                    "title_en": normalized["title_en"],
                    "title_ar": normalized["title_ar"],
                    "description_en": normalized["description_en"],
                    "description_ar": normalized["description_ar"],
                    "course_url": normalized["url"],
                    "platform": normalized["platform"],
                    "level": normalized["raw_level"],
                    "price": normalized["raw_price"],
                    "translation_status": normalized.get(
                        "translation_status", "pending"
                    ),
                }
            )

    def _normalize_candidate(self, item: dict):
        title_en = self._safe_text(item.get("title_en"))
        description_en = self._safe_text(item.get("description_en"))
        if not title_en:
            return None
        if not description_en:
            description_en = "[NEEDS RESEARCH]"

        title_ar = self._safe_text(item.get("title_ar")) or None
        description_ar = self._safe_text(item.get("description_ar")) or None
        platform_name = self._safe_text(item.get("platform")) or "Other"
        raw_level = self._safe_text(item.get("level")) or "intermediate"
        raw_price = self._safe_text(item.get("price"))
        url = (
            self._safe_text(item.get("url"))
            or self._safe_text(item.get("source_url"))
            or self._safe_text(item.get("access_link"))
            or "[NEEDS RESEARCH]"
        )

        translation_status = infer_translation_status(
            raw_status=self._safe_text(item.get("translation_status")) or "pending",
            english_values=[title_en, description_en],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "title_en": title_en[:200],
            "title_ar": title_ar[:200] if title_ar else None,
            "description_en": description_en,
            "description_ar": description_ar if description_ar else None,
            "platform_name": platform_name,
            "platform": self._map_platform(platform_name),
            "raw_level": raw_level,
            "academic_level": self._map_level(raw_level),
            "raw_price": raw_price,
            "is_free": self._is_free(raw_price),
            "price_decimal": self._parse_price(raw_price),
            "url": url,
            "keywords": ", ".join(["nlp", "ai", platform_name.lower()]),
            "language": "ar"
            if self._contains_arabic((title_ar or "") + " " + (description_ar or ""))
            else "en",
            "translation_status": translation_status,
        }

    def _resolve_institution(self, platform_name: str):
        country = self.get_or_create_country("International", "XX", "دولي")
        institution_name = platform_name.strip() or "Online Learning Platform"
        return self.get_or_create_institution(
            institution_name,
            country=country,
            city="Online",
            website="",
            inst_type="University",
        )

    def _default_academic_year(self) -> str:
        today = timezone.now().date()
        year = today.year
        if today.month < 9:
            year -= 1
        return f"{year}-{year + 1}"

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    def _map_level(self, raw_level: str) -> str:
        lowered = (raw_level or "").lower()
        for token, mapped in self.LEVEL_MAP.items():
            if token in lowered:
                return mapped
        return "master"

    def _map_platform(self, platform_name: str) -> str:
        lowered = (platform_name or "").lower()
        for token, mapped in self.PLATFORM_MAP.items():
            if token in lowered:
                return mapped
        return "other"

    @staticmethod
    def _contains_arabic(text: str) -> bool:
        return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))

    @staticmethod
    def _is_free(raw_price: str) -> bool:
        price_text = (raw_price or "").strip().lower()
        if not price_text:
            return True
        return price_text in {"free", "0", "$0", "0$", "مجاني", "null"}

    def _parse_price(self, raw_price: str):
        if self._is_free(raw_price):
            return None
        if not raw_price:
            return None

        digits = "".join(ch for ch in raw_price if ch.isdigit() or ch in {".", ","})
        if not digits:
            return None

        digits = digits.replace(",", ".")
        try:
            return Decimal(digits)
        except (InvalidOperation, ValueError):
            return None
