"""Custom source scraper using configured seed items and no HTTP parsing stack."""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.utils import timezone

from scraping.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


_DEFAULT_CATEGORY_KEYWORDS = {
    "events": ["conference", "workshop", "seminar", "cfp", "summit", "hackathon"],
    "tools": ["model", "dataset", "tool", "library", "huggingface", "github"],
    "courses": ["course", "mooc", "lecture", "curriculum", "training"],
}


class CustomDomainScraper(BaseScraper):
    """Persist curated items from source configuration without live HTTP fetching."""

    CATEGORY_KEYWORDS = _DEFAULT_CATEGORY_KEYWORDS

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.category = self._normalize_category(getattr(source, "category", ""))
        self.detected_category = None
        self.items_failed = 0

    def scrape(self):
        results = []
        base_url = (getattr(self.source, "base_url", "") or "").strip()
        resolved_category = self._resolve_effective_category(base_url, page_text="")
        self.category = resolved_category

        for raw_item in self._load_seed_items():
            normalized = self._normalize_item(raw_item)
            if normalized is None:
                self.items_failed += 1
                continue

            try:
                saved = self._save_item(normalized, resolved_category)
            except Exception as exc:
                self.items_failed += 1
                self._log_error(
                    "custom_scraper_save",
                    str(exc),
                    source=normalized.get("title") or "unknown",
                    url=normalized.get("url") or "",
                )
                continue

            if saved is None:
                self.items_skipped += 1
                continue

            results.append(saved)

        return results

    def _normalize_category(self, category):
        value = (category or "").strip().lower()
        return value if value in self.CATEGORY_KEYWORDS else ""

    def _resolve_effective_category(self, source_url, page_text=""):
        config = dict(getattr(self.source, "scrape_config", {}) or {})
        explicit_category = self._normalize_category(getattr(self.source, "category", ""))
        override_category = self._normalize_category(config.get("category_override", ""))
        auto_detect = bool(config.get("auto_detect_category", False))

        if override_category:
            return override_category

        if explicit_category and not auto_detect:
            return explicit_category

        detected = self._detect_category(source_url, page_text)
        if detected:
            self.detected_category = detected
            return detected

        return explicit_category or "events"

    def _detect_category(self, source_url, page_text):
        return self.detect_category_from_signals(source_url, page_text)

    def _extract_with_llm(self, page_text: str, category: str) -> list[dict]:
        """Optional lightweight extraction path used by custom-source scraping tests."""
        if not bool(getattr(self.source, "use_llm_extraction", False)):
            return []

        try:
            from scraping.extractors.core.llm_validation import (
                GroqLLMClient,
                build_custom_extraction_prompt,
            )

            system_prompt, user_prompt = build_custom_extraction_prompt(
                category or self.category,
                page_text or "",
            )
            client = GroqLLMClient()
            response = client._chat(system_prompt, user_prompt)
            if not response:
                return []
            parsed = json.loads(response)
            return parsed if isinstance(parsed, list) else []
        except Exception as exc:
            self._log_error(
                "llm_extraction_failed",
                str(exc),
                source=getattr(self.source, "name", "Custom Source"),
                url=getattr(self.source, "base_url", "") or "",
            )
            return []

    @classmethod
    def detect_category_from_signals(cls, source_url, page_text):
        url_text = (source_url or "").lower()
        body_text = (page_text or "").lower()
        combined = f"{url_text}\n{body_text}"

        scores = {category: 0 for category in cls.CATEGORY_KEYWORDS}
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                lowered = keyword.lower()
                if lowered in combined:
                    scores[category] += 1
                if lowered in url_text:
                    scores[category] += 2

        best_category = max(scores, key=scores.get)
        if scores[best_category] <= 0:
            return "events"
        return best_category

    def _load_seed_items(self) -> list[dict]:
        config = dict(getattr(self.source, "scrape_config", {}) or {})
        candidates = config.get("seed_items")
        if not isinstance(candidates, list):
            candidates = config.get("sample_items")
        if not isinstance(candidates, list):
            return []
        return [item for item in candidates if isinstance(item, dict)]

    def _normalize_item(self, item: dict):
        title = (item.get("title") or item.get("name") or "").strip()
        if not title:
            return None

        url = (item.get("url") or item.get("website") or item.get("link") or "").strip()
        description = (
            item.get("description")
            or item.get("summary")
            or item.get("what_it_does")
            or title
        )

        return {
            "title": title[:200],
            "name": title[:200],
            "description": str(description).strip(),
            "url": url,
            "date": item.get("date"),
            "event_type": (item.get("event_type") or "conference").strip().lower(),
            "location": (item.get("location") or "Online").strip(),
            "registration_link": (item.get("registration_link") or "").strip(),
            "tool_type": (item.get("tool_type") or item.get("task") or "tokenization").strip().lower(),
            "github_url": (item.get("github_url") or item.get("github_link") or "").strip(),
            "documentation_link": (item.get("documentation_link") or item.get("docs") or "").strip(),
            "institution": (item.get("institution") or item.get("provider") or "Global NLP Academy").strip(),
            "level": (item.get("level") or "master").strip().lower(),
            "instructor": (item.get("instructor") or item.get("teacher") or "NLP Platform Team").strip(),
            "platform": (item.get("platform") or "").strip(),
            "language": (item.get("language") or "en").strip().lower(),
            "duration": (item.get("duration") or "").strip(),
            "is_free": bool(item.get("is_free", True)),
        }

    def _save_item(self, item, category):
        category = (category or "").strip().lower()
        if category == "events":
            return self._save_as_event(item)
        if category == "tools":
            return self._save_as_tool(item)
        if category == "courses":
            return self._save_as_course(item)
        return None

    def _save_as_event(self, item):
        from events.models import Event

        title = item.get("title", "").strip()
        if not title:
            return None

        start_dt = self.parse_date(str(item.get("date") or ""))
        if start_dt is None:
            start_date = timezone.now().date() + timedelta(days=30)
        else:
            start_date = start_dt.date()

        organizer = self.get_or_create_institution(
            getattr(self.source, "name", "Custom Source") or "Custom Source",
            inst_type="Other",
            website=(item.get("url") or "").strip(),
        )
        if organizer is None:
            return None

        event_type = item.get("event_type") or "conference"
        if event_type not in {"conference", "workshop", "seminar", "call_for_papers", "hackathon"}:
            event_type = "conference"

        defaults = {
            "title": title,
            "title_en": title,
            "title_ar": title,
            "description": item.get("description") or title,
            "description_en": item.get("description") or title,
            "description_ar": item.get("description") or title,
            "event_type": event_type,
            "domains": "nlp,ai",
            "location": item.get("location") or "Online",
            "location_en": item.get("location") or "Online",
            "location_ar": item.get("location") or "Online",
            "start_date": start_date,
            "end_date": start_date,
            "website": item.get("url") or "",
            "registration_link": item.get("registration_link") or item.get("url") or "",
            "source_url": item.get("url") or "",
            "source_name": getattr(self.source, "name", "Custom Source"),
            "language": "ar" if item.get("language") == "ar" else "en",
            "tags": ["custom_source", "events"],
            "entities": {"category": "events"},
            "contact_email": "scraper-bot@nlp-platform.local",
            "organizer": organizer,
            "created_by": self.get_system_user(),
            "approval_status": "pending",
            "source": "scrape",
        }

        Event.objects.update_or_create(
            title_en=title,
            start_date=start_date,
            defaults=defaults,
        )

        self.items_created += 1

        mapped = {
            "title": defaults["title_en"],
            "description": self.truncate(defaults["description_en"], 400),
            "type": defaults["event_type"],
            "url": defaults["website"],
            "source_name": defaults["source_name"],
            "source_url": defaults["source_url"],
            "title_en": defaults["title_en"],
            "description_en": defaults["description_en"],
        }
        self.results.append(mapped)
        return mapped

    def _save_as_tool(self, item):
        from resources.models import NLPTool

        title = item.get("title", "").strip()
        if not title:
            return None

        tool_type = item.get("tool_type") or "tokenization"
        if tool_type not in {
            "tokenization",
            "stemming",
            "ner",
            "pos_tagging",
            "sentiment_analysis",
            "machine_translation",
        }:
            tool_type = "tokenization"

        supported_language = item.get("language")
        if supported_language not in {"ar", "en", "fr", "es"}:
            supported_language = "ar"

        defaults = {
            "title": title,
            "title_en": title,
            "title_ar": title,
            "description": item.get("description") or title,
            "description_en": item.get("description") or title,
            "description_ar": item.get("description") or title,
            "author": self.get_system_user(),
            "tool_type": tool_type,
            "version": "1.0.0",
            "documentation_link": item.get("documentation_link") or "",
            "github_url": item.get("github_url") or "",
            "source_url": item.get("url") or "",
            "source_name": getattr(self.source, "name", "Custom Source"),
            "supported_languages": supported_language,
            "access_link": item.get("url") or "",
            "keywords": "custom, tool",
            "entities": {"category": "tools"},
            "language": "ar" if supported_language == "ar" else "en",
            "approval_status": "pending",
            "is_approved": False,
            "update_date": timezone.now(),
        }

        NLPTool.objects.update_or_create(
            title_en=title,
            defaults=defaults,
        )

        self.items_created += 1

        mapped = {
            "title": defaults["title_en"],
            "description": self.truncate(defaults["description_en"], 400),
            "type": defaults["tool_type"],
            "url": defaults["access_link"],
            "source_name": defaults["source_name"],
            "source_url": defaults["source_url"],
            "title_en": defaults["title_en"],
            "description_en": defaults["description_en"],
        }
        self.results.append(mapped)
        return mapped

    def _save_as_course(self, item):
        from resources.models import Course

        title = item.get("title", "").strip()
        if not title:
            return None

        level = item.get("level") or "master"
        if level not in {"bachelor", "master", "doctorate"}:
            if "begin" in level:
                level = "bachelor"
            elif "adv" in level or "phd" in level:
                level = "doctorate"
            else:
                level = "master"

        access_link = item.get("url") or ""
        institution = self.get_or_create_institution(
            item.get("institution") or "Global NLP Academy",
            inst_type="University",
            website=access_link,
        )
        if institution is None:
            return None

        today = timezone.now().date()
        start_year = today.year if today.month >= 9 else today.year - 1
        academic_year = f"{start_year}-{start_year + 1}"

        defaults = {
            "title": title,
            "title_en": title,
            "title_ar": title,
            "description": item.get("description") or title,
            "description_en": item.get("description") or title,
            "description_ar": item.get("description") or title,
            "author": self.get_system_user(),
            "field": "nlp",
            "academic_level": level,
            "teacher": self.get_system_user(),
            "institution": institution,
            "academic_year": academic_year,
            "prerequisites": "",
            "syllabus": "",
            "instructor": item.get("instructor") or "NLP Platform Team",
            "duration": item.get("duration") or "",
            "platform": self._normalize_course_platform(item.get("platform"), access_link),
            "enrollment_url": access_link,
            "is_free": bool(item.get("is_free", True)),
            "source_url": access_link,
            "source_name": getattr(self.source, "name", "Custom Source"),
            "access_link": access_link,
            "keywords": "custom, course",
            "entities": {"category": "courses"},
            "language": "ar" if item.get("language") == "ar" else "en",
            "approval_status": "pending",
            "is_approved": False,
            "update_date": timezone.now(),
        }

        Course.objects.update_or_create(
            title_en=title,
            access_link=access_link,
            defaults=defaults,
        )

        self.items_created += 1

        mapped = {
            "title": defaults["title_en"],
            "description": self.truncate(defaults["description_en"], 400),
            "type": "course",
            "url": defaults["access_link"],
            "source_name": defaults["source_name"],
            "source_url": defaults["source_url"],
            "title_en": defaults["title_en"],
            "description_en": defaults["description_en"],
        }
        self.results.append(mapped)
        return mapped

    def _normalize_course_platform(self, platform: str, url: str) -> str:
        candidate = (platform or "").strip().lower()
        if candidate in {"coursera", "youtube", "mit", "edx", "university", "other"}:
            return candidate

        lowered_url = (url or "").lower()
        if "coursera" in lowered_url:
            return "coursera"
        if "youtube" in lowered_url or "youtu.be" in lowered_url:
            return "youtube"
        if "edx" in lowered_url:
            return "edx"
        return "university"
