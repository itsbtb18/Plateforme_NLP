"""
NLP Courses scraper — sources: MIT OpenCourseWare API, Coursera catalog,
YouTube NLP playlists, and curated list of well-known NLP courses
from top universities.

Each scraped course is stored as a ``resources.Course`` instance with
``approval_status='pending'``.
"""

import logging
import re
from datetime import date
from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import (
    try_download_document,
    attach_file_to_model,
)
from scraping.field_mapping import calculate_completeness_score

logger = logging.getLogger(__name__)

# ── Field keyword → FieldChoices mapping ─────────────────────────────
FIELD_MAP = {
    "nlp": "nlp",
    "natural language": "nlp",
    "computational linguistics": "comp_linguistics",
    "machine learning": "ml",
    "deep learning": "ml",
    "artificial intelligence": "ai",
    "speech": "speech_processing",
    "information retrieval": "ir",
    "text mining": "text_mining",
    "data science": "data_science",
    "linguistics": "linguistics",
    "sentiment": "sentiment_analysis",
    "translation": "translation",
    "named entity": "named_entity",
    "arabic": "arabic_linguistics",
}

import json
import os

def _load_curated_courses():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'fixtures', 'curated_courses.json'
    )
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

_courses_data = _load_curated_courses()

# ── Curated NLP courses from top universities ────────────────────────
CURATED_COURSES = _courses_data.get('university_courses', [])


class CourseScraper(BaseScraper):
    """Scrape / import NLP courses from curated list and MIT OCW API."""

    name = "NLP Courses"
    category = "courses"

    def scrape(self):
        self._scrape_mit_ocw()
        self._scrape_coursera()
        self._import_youtube_playlists()
        self._import_curated_courses()

    # ── MIT OpenCourseWare (via MIT Open Learning API) ──────────────
    MIT_API_BASE = "https://api.learn.mit.edu/api/v1/courses/"

    # Targeted queries to find NLP / AI / computational-linguistics courses
    MIT_QUERIES = [
        {"q": "natural language processing", "topic": "AI", "limit": 10},
        {"q": "computational linguistics", "offered_by": "ocw", "limit": 5},
        {"q": "deep learning", "topic": "AI", "limit": 10},
        {"q": "machine learning NLP", "topic": "AI", "limit": 5},
        {"q": "text mining information retrieval", "offered_by": "ocw", "limit": 5},
    ]

    def _scrape_mit_ocw(self):
        """Scrape NLP-related courses from the MIT Open Learning API."""
        seen_ids: set[int] = set()

        mit_country = self.get_or_create_country("United States", "US")
        mit_inst = self.get_or_create_institution(
            "Massachusetts Institute of Technology",
            acronym="MIT",
            country=mit_country,
            city="Cambridge, Massachusetts",
            website="https://ocw.mit.edu",
            inst_type="University",
        )
        if mit_inst is None:
            return

        for query_params in self.MIT_QUERIES:
            params = {"offered_by": "ocw", **query_params}
            resp = self.safe_request(
                self.MIT_API_BASE,
                params=params,
                headers={"Accept": "application/json"},
            )
            if resp is None:
                continue

            try:
                data = resp.json()
                results = data.get("results", [])
                if not isinstance(results, list):
                    continue

                for course in results:
                    course_id = course.get("id")
                    if course_id in seen_ids:
                        continue
                    seen_ids.add(course_id)

                    title = course.get("title", "")
                    if not title:
                        continue

                    desc = self.clean_text(course.get("description", ""))
                    course_url = course.get("url", "")
                    if course_url and not course_url.startswith("http"):
                        course_url = f"https://ocw.mit.edu{course_url}"

                    # Resolve level from first run
                    level = "master"
                    runs = course.get("runs", [])
                    if runs:
                        levels = runs[0].get("level", [])
                        if levels:
                            code = levels[0].get("code", "")
                            if code == "undergraduate":
                                level = "bachelor"
                            elif code == "graduate":
                                level = "master"

                    self._create_course(
                        title=title,
                        description=desc,
                        institution=mit_inst,
                        website=course_url,
                        field="nlp",
                        level=level,
                    )
            except Exception as exc:
                self.errors.append(f"MIT OCW parse error: {exc}")
                logger.error("MIT OCW parse error: %s", exc)

    # ── Coursera NLP Courses ────────────────────────────────────────
    COURSERA_COURSES = _courses_data.get('coursera_courses', [])

    def _scrape_coursera(self):
        """Import Coursera NLP-related courses from curated catalog."""
        for item in self.COURSERA_COURSES:
            country = self.get_or_create_country(
                item["institution"][:30],
                item.get("country", "US"),
            )
            institution = self.get_or_create_institution(
                item["institution"],
                country=country,
                city=item.get("city", ""),
                website=item.get("link", ""),
                inst_type="Other",
            )
            if institution is None:
                self.items_skipped += 1
                continue

            desc = item["description"]
            if item.get("instructor"):
                desc += f"\n\nInstructor: {item['instructor']}"
            if item.get("duration"):
                desc += f"\nDuration: {item['duration']}"

            self._create_course(
                title=item["title"],
                description=desc,
                institution=institution,
                website=item["link"],
                field="nlp",
                level=item.get("level", "bachelor"),
            )

    # ── YouTube NLP Playlists ─────────────────────────────────────────
    YOUTUBE_PLAYLISTS = _courses_data.get('youtube_playlists', [])

    def _import_youtube_playlists(self):
        """Import YouTube NLP playlists as courses."""
        yt_country = self.get_or_create_country("International", "XX")
        yt_inst = self.get_or_create_institution(
            "YouTube Educational Content",
            country=yt_country,
            website="https://www.youtube.com",
            inst_type="Other",
        )
        if yt_inst is None:
            return

        for item in self.YOUTUBE_PLAYLISTS:
            desc = item["description"]
            if item.get("instructor"):
                desc += f"\n\nInstructor: {item['instructor']}"
            if item.get("duration"):
                desc += f"\nDuration: {item['duration']}"

            self._create_course(
                title=item["title"],
                description=desc,
                institution=yt_inst,
                website=item["link"],
                field="nlp",
                level=item.get("level", "bachelor"),
            )

    # ── Curated courses ───────────────────────────────────────────────
    def _import_curated_courses(self):
        """Import well-known NLP courses from the curated list."""
        for item in CURATED_COURSES:
            country = self.get_or_create_country(
                item["institution_name"][:30],
                item.get("institution_country", "US"),
            )
            institution = self.get_or_create_institution(
                item["institution_name"],
                country=country,
                city=item.get("institution_city", ""),
                website=item.get("website", ""),
                inst_type="University",
            )
            if institution is None:
                self.items_skipped += 1
                continue

            self._create_course(
                title=item["title"],
                description=item["description"],
                institution=institution,
                website=item.get("website", ""),
                field=item.get("field", "nlp"),
                level=item.get("level", "master"),
                prerequisites=item.get("prerequisites", ""),
                syllabus=item.get("syllabus", ""),
            )

    # ── Helper ────────────────────────────────────────────────────────
    def _create_course(
        self,
        *,
        title,
        description,
        institution,
        website="",
        field="nlp",
        level="master",
        prerequisites="",
        syllabus="",
        end_date=None,
        last_updated=None,
    ):
        from resources.models import Course

        title_en = title

        # Freshness filter — skip expired or very outdated courses
        if not self.is_course_still_available(
            end_date=end_date,
            last_updated=last_updated,
            max_age_days=730,
        ):
            self.items_skipped += 1
            return

        # Duplicate check
        if self.is_duplicate(title_en, "courses", Course):
            self.items_skipped += 1
            return

        import datetime

        current_year = datetime.datetime.now().year
        academic_year = f"{current_year}-{current_year + 1}"

        title_ar = title
        description_en = description
        description_ar = description
        field_of_study = field
        academic_level = level
        teaching_language = "english"
        course_url = website
        keywords = [
            "nlp",
            "natural language processing",
            "deep learning",
        ]
        syllabus_file_url = ""

        item_dict = {
            "title_en": title_en,
            "title_ar": title_ar,
            "description_en": description_en,
            "description_ar": description_ar,
            "field_of_study": field_of_study,
            "academic_level": academic_level,
            "teaching_language": teaching_language,
            "course_url": course_url,
            "keywords": keywords,
            "prerequisites": prerequisites,
            "syllabus": syllabus,
            "academic_year": academic_year,
            "syllabus_file_url": syllabus_file_url,
        }

        item_dict = enrich_scraped_item(item_dict, "courses")
        completeness = calculate_completeness_score(item_dict, "courses")

        if completeness < 40:
            self.items_skipped += 1
            return

        is_valid, item_dict, reason = self.validate_and_prepare(item_dict, "courses")
        if not is_valid:
            self.items_skipped += 1
            logger.debug("Skipping course '%s' due to validation: %s", title, reason)
            return

        model_language = "en"
        if str(item_dict.get("teaching_language", "english")).lower() == "arabic":
            model_language = "ar"

        try:
            course = Course.objects.create(
                title=item_dict.get("title_en", "")[:300],
                title_en=item_dict.get("title_en", "")[:300],
                title_ar=item_dict.get("title_ar", "")[:300],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                field=item_dict.get("field_of_study", "nlp"),
                academic_level=item_dict.get("academic_level", "master"),
                teacher=self.get_system_user(),
                institution=institution,
                academic_year=item_dict.get("academic_year", academic_year),
                access_link=item_dict.get("course_url", ""),
                language=model_language,
                keywords=", ".join(
                    item_dict.get("keywords", [])
                    if isinstance(item_dict.get("keywords"), list)
                    else [str(item_dict.get("keywords", ""))]
                ),
                prerequisites=item_dict.get("prerequisites", ""),
                syllabus=item_dict.get("syllabus", ""),
                author=self.get_system_user(),
                approval_status="pending",
            )

            # Download syllabus PDF
            syllabus_url = item_dict.get("syllabus_file_url", "")
            if syllabus_url:
                doc_file, filename = try_download_document([syllabus_url], "courses")
                if doc_file:
                    try:
                        attach_file_to_model(
                            course, "uploaded_file", doc_file, filename
                        )
                    except Exception:
                        pass

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 100),
                    "institution": institution.name_en,
                    "level": item_dict.get("academic_level", level),
                    "url": item_dict.get("course_url", website),
                }
            )
        except Exception as exc:
            self.errors.append(
                f"Failed to create course '{item_dict.get('title_en', title)}': {exc}"
            )
            logger.error(
                "Failed to create Course %s: %s", item_dict.get("title_en", title), exc
            )
