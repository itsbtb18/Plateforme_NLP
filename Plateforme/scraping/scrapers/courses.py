"""
Tiered NLP/AI courses scraper.

Priority policy:
1) Algerian sources
2) Arabic/MENA sources
3) Global sources

Each scraped item is stored as resources.Course with approval_status='pending'.
"""

import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.field_mapping import calculate_completeness_score
from scraping.file_downloader import (
    attach_file_to_model,
)

logger = logging.getLogger(__name__)


def _load_curated_courses():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "fixtures", "curated_courses.json"
    )
    try:
        with open(fixture_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


_FIXTURE_DATA = _load_curated_courses()

# Global curated fallbacks kept as additional coverage.
CURATED_COURSES = _FIXTURE_DATA.get("university_courses", [])
COURSERA_COURSES = _FIXTURE_DATA.get("coursera_courses", [])
YOUTUBE_PLAYLISTS = _FIXTURE_DATA.get("youtube_playlists", [])

FIELD_MAP = {
    "nlp": "nlp",
    "natural language": "nlp",
    "machine learning": "ml",
    "deep learning": "ml",
    "intelligence artificielle": "ai",
    "artificial intelligence": "ai",
    "informatique": "computer_science",
    "data science": "data_science",
    "speech": "speech_processing",
    "text mining": "text_mining",
    "information retrieval": "ir",
    "arabic": "arabic_linguistics",
    "linguistics": "linguistics",
    "translation": "translation",
}

LEVEL_HINTS = {
    "beginner": "bachelor",
    "intro": "bachelor",
    "foundation": "bachelor",
    "intermediate": "master",
    "advanced": "master",
    "expert": "doctorate",
    "doctoral": "doctorate",
}

PRICE_PATTERN = re.compile(
    r"(?:(?:USD|EUR|DZD|\$|€)\s?\d+(?:[\.,]\d{1,2})?|\d+(?:[\.,]\d{1,2})?\s?(?:USD|EUR|DZD|\$|€))",
    re.I,
)

DURATION_PATTERN = re.compile(
    r"(\d+\+?\s*(?:weeks?|week|hours?|hrs?|heures?|h|videos?|lectures?|ساعات?|ساعة|أسبوع(?:ين)?))",
    re.I,
)

START_DATE_PATTERN = re.compile(
    r"(?:starts?|begins?|start date|commence|debute|يبدأ|تبدأ|ينطلق)\s*[:\-]?\s*([A-Za-z0-9\-/,. ]{4,40})",
    re.I,
)


class CourseScraper(BaseScraper):
    name = "NLP Courses"
    category = "courses"

    def run(self) -> dict:
        logger.info(
            "scraper_run_config",
            extra={
                "category": self.category,
                "source_name": self.name,
                "media_download_enabled": self._is_download_enabled(),
            },
        )
        return super().run()

    ALGERIAN_UNIVERSITY_OCW = [
        "https://elearning.univ-alger.dz",
        "https://elearning.usthb.dz",
        "https://elearning.esi.dz",
        "https://elearning.umc.edu.dz",
    ]
    ALGERIAN_OCW_PATHS = ["/courses", "/matieres", "/modules"]

    CERIST_FORMATION_URL = "https://www.cerist.dz/formation"

    YOUTUBE_SEARCH_TERMS_TIER_1 = [
        "دروس البرمجة الجزائر",
        "machine learning arabic Algeria",
        "NLP arabic course",
    ]

    FUN_MOOC_API = "https://www.fun-mooc.fr/api/v1.0/courses/?format=json"

    COURSERA_ARABIC_TERMS = [
        "Arabic NLP",
        "تعلم الآلة",
        "معالجة اللغة الطبيعية",
        "ذكاء اصطناعي",
    ]

    RWAQ_URL = "https://www.rwaq.org"
    EDRAAK_URL = "https://www.edraak.org"

    MIT_API_BASE = "https://api.learn.mit.edu/api/v1/courses/"

    FASTAI_URLS = ["https://course.fast.ai", "https://www.fast.ai/posts/"]
    HF_LEARN_URL = "https://huggingface.co/learn"
    DEEPLEARNING_AI_COURSES = "https://www.deeplearning.ai/courses/"

    AI_NLP_KEYWORDS = (
        "nlp",
        "natural language",
        "language model",
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "apprentissage automatique",
        "intelligence artificielle",
        "informatique",
        "data science",
        "programm",
        "arabic",
        "معالجة اللغة",
        "ذكاء",
        "تعلم الآلة",
        "برمجة",
    )

    TIER_1_RSS_SOURCES = [
        {
            "base_url": "https://elearning.univ-alger.dz",
            "source_name": "Univ Alger eLearning",
            "institution_name": "University of Algiers eLearning",
            "country_name": "Algeria",
            "country_code": "DZ",
            "inst_type": "University",
        },
        {
            "base_url": "https://elearning.usthb.dz",
            "source_name": "USTHB eLearning",
            "institution_name": "USTHB eLearning",
            "country_name": "Algeria",
            "country_code": "DZ",
            "inst_type": "University",
        },
        {
            "base_url": "https://www.cerist.dz",
            "source_name": "CERIST",
            "institution_name": "CERIST",
            "country_name": "Algeria",
            "country_code": "DZ",
            "inst_type": "Research Center",
        },
    ]

    TIER_2_RSS_SOURCES = [
        {
            "base_url": "https://www.edraak.org",
            "source_name": "Edraak",
            "institution_name": "Edraak",
            "country_name": "Jordan",
            "country_code": "JO",
            "inst_type": "Other",
        },
        {
            "base_url": "https://www.rwaq.org",
            "source_name": "Rwaq",
            "institution_name": "Rwaq",
            "country_name": "Saudi Arabia",
            "country_code": "SA",
            "inst_type": "Other",
        },
    ]

    TIER_3_RSS_SOURCES = [
        {
            "base_url": "https://ocw.mit.edu",
            "source_name": "MIT OCW",
            "institution_name": "Massachusetts Institute of Technology",
            "country_name": "United States",
            "country_code": "US",
            "inst_type": "University",
        },
        {
            "base_url": "https://course.fast.ai",
            "source_name": "fast.ai",
            "institution_name": "fast.ai",
            "country_name": "United States",
            "country_code": "US",
            "inst_type": "Other",
        },
        {
            "base_url": "https://huggingface.co/learn",
            "source_name": "Hugging Face Learn",
            "institution_name": "Hugging Face",
            "country_name": "United States",
            "country_code": "US",
            "inst_type": "Other",
        },
    ]

    def scrape(self):
        self._scrape_tier_1_algerian_courses()
        self._scrape_tier_2_arabic_courses()
        self._scrape_tier_3_global_courses()

    # ------------------------------------------------------------------
    # Tier 1 — Algerian
    # ------------------------------------------------------------------

    def _scrape_tier_1_algerian_courses(self):
        self._scrape_rss_course_sources(self.TIER_1_RSS_SOURCES)
        self._scrape_algerian_university_ocw()
        self._scrape_cerist_training_programs()
        self._scrape_youtube_playlists(
            self.YOUTUBE_SEARCH_TERMS_TIER_1, source_name="YouTube Algeria/Arabic"
        )
        self._scrape_fun_mooc_fr()

    def _scrape_algerian_university_ocw(self):
        for base_url in self.ALGERIAN_UNIVERSITY_OCW:
            domain = urlparse(base_url).netloc
            institution_name = domain.replace("elearning.", "").replace("www.", "")
            institution = self._ensure_institution(
                name=f"{institution_name} eLearning",
                website=base_url,
                country_name="Algeria",
                country_code="DZ",
                inst_type="University",
            )
            if institution is None:
                continue

            listing_urls = [base_url.rstrip("/")]
            listing_urls.extend(
                urljoin(base_url.rstrip("/") + "/", p.lstrip("/"))
                for p in self.ALGERIAN_OCW_PATHS
            )

            seen_urls: set[str] = set()
            for listing_url in listing_urls:
                resp = self.safe_request(listing_url, timeout=10, source_name=domain)
                if resp is None:
                    continue

                cards = self._extract_catalog_cards(resp.text, listing_url)
                for card in cards:
                    url = (card.get("url") or "").strip()
                    if not url:
                        continue
                    key = url.rstrip("/")
                    if key in seen_urls:
                        continue
                    seen_urls.add(key)

                    if not self._is_ai_nlp_related(
                        f"{card.get('title', '')} {card.get('description', '')}"
                    ):
                        continue

                    metadata = self._build_course_metadata(
                        title=card.get("title", ""),
                        description=card.get("description", ""),
                        source_url=url,
                        page_html=card.get("raw_html", ""),
                    )
                    self._create_course(
                        title=card.get("title", ""),
                        description=card.get("description", ""),
                        institution=institution,
                        website=url,
                        field=metadata["field"],
                        level=metadata["level"],
                        instructor=metadata["instructor"],
                        duration=metadata["duration"],
                        platform="university",
                        enrollment_url=metadata["enrollment_url"] or url,
                        thumbnail_url=metadata["thumbnail_url"],
                        is_free=metadata["is_free"],
                        price=metadata["price"],
                        certificate_available=metadata["certificate_available"],
                        start_date=metadata["start_date"],
                        source_url=url,
                        source_name=domain,
                    )

    def _scrape_cerist_training_programs(self):
        institution = self._ensure_institution(
            name="CERIST",
            website="https://www.cerist.dz",
            country_name="Algeria",
            country_code="DZ",
            city="Algiers",
            inst_type="Research Center",
        )
        if institution is None:
            return

        resp = self.safe_request(
            self.CERIST_FORMATION_URL, timeout=10, source_name="CERIST"
        )
        if resp is None:
            return

        cards = self._extract_catalog_cards(resp.text, self.CERIST_FORMATION_URL)
        if not cards:
            cards = self._extract_list_items_as_courses(
                resp.text, self.CERIST_FORMATION_URL
            )

        for card in cards:
            content = f"{card.get('title', '')} {card.get('description', '')}"
            if not self._is_ai_nlp_related(content):
                continue

            metadata = self._build_course_metadata(
                title=card.get("title", ""),
                description=card.get("description", ""),
                source_url=card.get("url") or self.CERIST_FORMATION_URL,
                page_html=card.get("raw_html", ""),
            )
            self._create_course(
                title=card.get("title", ""),
                description=card.get("description", ""),
                institution=institution,
                website=card.get("url") or self.CERIST_FORMATION_URL,
                field=metadata["field"],
                level=metadata["level"],
                instructor=metadata["instructor"],
                duration=metadata["duration"],
                platform="university",
                enrollment_url=metadata["enrollment_url"]
                or card.get("url")
                or self.CERIST_FORMATION_URL,
                thumbnail_url=metadata["thumbnail_url"],
                is_free=metadata["is_free"],
                price=metadata["price"],
                certificate_available=metadata["certificate_available"],
                start_date=metadata["start_date"],
                source_url=card.get("url") or self.CERIST_FORMATION_URL,
                source_name="CERIST",
            )

    def _scrape_fun_mooc_fr(self):
        resp = self.safe_request(
            self.FUN_MOOC_API,
            timeout=15,
            source_name="FUN MOOC",
            headers={"Accept": "application/json"},
        )
        if resp is None:
            return

        try:
            payload = resp.json()
        except Exception:
            return

        courses = []
        if isinstance(payload, dict):
            for key in ("results", "objects", "courses"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    courses = candidate
                    break
        if not courses and isinstance(payload, list):
            courses = payload

        fun_inst = self._ensure_institution(
            name="France Universite Numerique",
            website="https://www.fun-mooc.fr",
            country_name="France",
            country_code="FR",
            inst_type="Other",
        )
        if fun_inst is None:
            return

        subject_terms = (
            "informatique",
            "intelligence artificielle",
            "apprentissage automatique",
        )
        for item in courses:
            title = str(item.get("title") or item.get("name") or "").strip()
            description = str(
                item.get("description") or item.get("short_description") or ""
            ).strip()
            subject_blob = " ".join(
                [
                    str(item.get("subject") or ""),
                    str(item.get("subjects") or ""),
                    title,
                    description,
                ]
            ).lower()

            language = str(item.get("language") or item.get("lang") or "").lower()
            if language and not language.startswith("fr"):
                continue
            if not any(term in subject_blob for term in subject_terms):
                continue

            course_url = (
                item.get("url")
                or item.get("absolute_url")
                or item.get("course_url")
                or ""
            )
            if course_url and not str(course_url).startswith("http"):
                course_url = urljoin("https://www.fun-mooc.fr", str(course_url))

            metadata = self._build_course_metadata(
                title=title,
                description=description,
                source_url=course_url,
                page_html="",
            )
            self._create_course(
                title=title,
                description=description,
                institution=fun_inst,
                website=course_url,
                field=metadata["field"],
                level=metadata["level"],
                instructor=metadata["instructor"],
                duration=metadata["duration"],
                platform="other",
                enrollment_url=metadata["enrollment_url"] or course_url,
                thumbnail_url=item.get("image")
                or item.get("thumbnail")
                or metadata["thumbnail_url"],
                is_free=metadata["is_free"],
                price=metadata["price"],
                certificate_available=metadata["certificate_available"],
                start_date=metadata["start_date"],
                source_url=course_url,
                source_name="FUN MOOC",
            )

    # ------------------------------------------------------------------
    # Tier 2 — Arabic
    # ------------------------------------------------------------------

    def _scrape_tier_2_arabic_courses(self):
        self._scrape_rss_course_sources(self.TIER_2_RSS_SOURCES)
        self._scrape_coursera_arabic_queries()
        self._scrape_rwaq_courses()
        self._scrape_edraak_courses()

    def _scrape_coursera_arabic_queries(self):
        institution = self._ensure_institution(
            name="Coursera",
            website="https://www.coursera.org",
            country_name="International",
            country_code="XX",
            inst_type="Other",
        )
        if institution is None:
            return

        seen_urls: set[str] = set()

        # Curated fallback entries first
        for item in COURSERA_COURSES:
            url = str(item.get("link") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            blob = f"{item.get('title', '')} {item.get('description', '')}"
            if not self._is_ai_nlp_related(blob):
                continue

            metadata = self._build_course_metadata(
                title=item.get("title", ""),
                description=item.get("description", ""),
                source_url=url,
                page_html="",
                instructor_hint=item.get("instructor", ""),
                duration_hint=item.get("duration", ""),
            )
            self._create_course(
                title=item.get("title", ""),
                description=item.get("description", ""),
                institution=institution,
                website=url,
                field=metadata["field"],
                level=item.get("level") or metadata["level"],
                instructor=item.get("instructor") or metadata["instructor"],
                duration=item.get("duration") or metadata["duration"],
                platform="coursera",
                enrollment_url=metadata["enrollment_url"] or url,
                thumbnail_url=item.get("thumbnail_url") or metadata["thumbnail_url"],
                is_free=bool(item.get("is_free", metadata["is_free"])),
                price=self._parse_price(item.get("price")) or metadata["price"],
                certificate_available=bool(
                    item.get("certificate_available", metadata["certificate_available"])
                ),
                start_date=metadata["start_date"],
                source_url=url,
                source_name="Coursera",
            )

        # Targeted Arabic search pages
        for term in self.COURSERA_ARABIC_TERMS:
            search_url = f"https://www.coursera.org/search?query={quote_plus(term)}"
            resp = self.safe_request(search_url, timeout=10, source_name="Coursera")
            if resp is None:
                continue

            cards = self._extract_catalog_cards(resp.text, search_url)
            for card in cards:
                url = (card.get("url") or "").strip()
                if not url:
                    continue
                if "coursera.org" not in url:
                    continue
                if (
                    "/learn/" not in url
                    and "/specializations/" not in url
                    and "/professional-certificates/" not in url
                ):
                    continue
                key = url.rstrip("/")
                if key in seen_urls:
                    continue
                seen_urls.add(key)

                metadata = self._build_course_metadata(
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    source_url=url,
                    page_html=card.get("raw_html", ""),
                )
                self._create_course(
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    institution=institution,
                    website=url,
                    field=metadata["field"],
                    level=metadata["level"],
                    instructor=metadata["instructor"],
                    duration=metadata["duration"],
                    platform="coursera",
                    enrollment_url=metadata["enrollment_url"] or url,
                    thumbnail_url=metadata["thumbnail_url"],
                    is_free=metadata["is_free"],
                    price=metadata["price"],
                    certificate_available=metadata["certificate_available"],
                    start_date=metadata["start_date"],
                    source_url=url,
                    source_name=f"Coursera search: {term}",
                )

    def _scrape_rwaq_courses(self):
        self._scrape_generic_mooc_site(
            base_url=self.RWAQ_URL,
            source_name="Rwaq",
            country_name="Saudi Arabia",
            country_code="SA",
        )

    def _scrape_edraak_courses(self):
        self._scrape_generic_mooc_site(
            base_url=self.EDRAAK_URL,
            source_name="Edraak",
            country_name="Jordan",
            country_code="JO",
        )

    def _scrape_generic_mooc_site(
        self, *, base_url: str, source_name: str, country_name: str, country_code: str
    ):
        institution = self._ensure_institution(
            name=source_name,
            website=base_url,
            country_name=country_name,
            country_code=country_code,
            inst_type="Other",
        )
        if institution is None:
            return

        candidate_urls = [base_url, urljoin(base_url.rstrip("/") + "/", "courses")]
        seen: set[str] = set()
        for listing_url in candidate_urls:
            resp = self.safe_request(listing_url, timeout=10, source_name=source_name)
            if resp is None:
                continue

            cards = self._extract_catalog_cards(resp.text, listing_url)
            for card in cards:
                combined = (
                    f"{card.get('title', '')} {card.get('description', '')}".lower()
                )
                if not self._is_ai_nlp_related(combined):
                    continue

                course_url = (card.get("url") or "").strip()
                if not course_url:
                    continue
                key = course_url.rstrip("/")
                if key in seen:
                    continue
                seen.add(key)

                metadata = self._build_course_metadata(
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    source_url=course_url,
                    page_html=card.get("raw_html", ""),
                )
                self._create_course(
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    institution=institution,
                    website=course_url,
                    field=metadata["field"],
                    level=metadata["level"],
                    instructor=metadata["instructor"],
                    duration=metadata["duration"],
                    platform="other",
                    enrollment_url=metadata["enrollment_url"] or course_url,
                    thumbnail_url=metadata["thumbnail_url"],
                    is_free=metadata["is_free"],
                    price=metadata["price"],
                    certificate_available=metadata["certificate_available"],
                    start_date=metadata["start_date"],
                    source_url=course_url,
                    source_name=source_name,
                )

    # ------------------------------------------------------------------
    # Tier 3 — Global
    # ------------------------------------------------------------------

    def _scrape_tier_3_global_courses(self):
        self._scrape_rss_course_sources(self.TIER_3_RSS_SOURCES)
        self._scrape_mit_ocw()
        self._scrape_fast_ai()
        self._scrape_huggingface_course()
        self._scrape_deeplearning_ai()
        self._import_youtube_fixture_playlists()
        self._import_curated_courses()

    def _scrape_rss_course_sources(self, sources: list[dict]):
        rss = self.get_rss_scraper()
        for source in sources:
            institution = self._ensure_institution(
                name=source.get("institution_name") or source.get("source_name") or "",
                website=source.get("base_url") or "",
                country_name=source.get("country_name") or "International",
                country_code=(source.get("country_code") or "XX")[:2].upper(),
                inst_type=source.get("inst_type") or "Other",
            )
            if institution is None:
                continue

            base_url = source.get("base_url") or ""
            source_name = source.get("source_name") or "RSS Courses"
            for feed_url in rss.auto_discover_feeds(base_url):
                items = rss.parse_feed_items(feed_url, max_items=40)
                for item in items:
                    title = self.clean_text(item.get("title") or "")
                    description = self.clean_text(item.get("description") or "")
                    course_url = (item.get("url") or "").strip()
                    if not title or not course_url:
                        continue
                    if not self._is_ai_nlp_related(f"{title} {description}"):
                        continue

                    metadata = self._build_course_metadata(
                        title=title,
                        description=description,
                        source_url=course_url,
                        page_html="",
                        instructor_hint=item.get("author") or "",
                    )
                    self._create_course(
                        title=title,
                        description=description,
                        institution=institution,
                        website=course_url,
                        field=metadata["field"],
                        level=metadata["level"],
                        instructor=metadata["instructor"] or (item.get("author") or ""),
                        duration=metadata["duration"],
                        platform=self._infer_platform(course_url),
                        enrollment_url=metadata["enrollment_url"] or course_url,
                        thumbnail_url=item.get("image_url")
                        or metadata["thumbnail_url"],
                        is_free=metadata["is_free"],
                        price=metadata["price"],
                        certificate_available=metadata["certificate_available"],
                        start_date=metadata["start_date"]
                        or self.parse_date(str(item.get("published_date") or "")[:10]),
                        source_url=feed_url,
                        source_name=f"RSS {source_name}",
                    )

    def _scrape_mit_ocw(self):
        queries = [
            {"q": "natural language processing", "topic": "AI", "limit": 10},
            {"q": "machine learning", "topic": "AI", "limit": 10},
            {"q": "deep learning", "topic": "AI", "limit": 10},
        ]

        institution = self._ensure_institution(
            name="Massachusetts Institute of Technology",
            website="https://ocw.mit.edu",
            country_name="United States",
            country_code="US",
            city="Cambridge",
            inst_type="University",
        )
        if institution is None:
            return

        seen_ids: set[str] = set()
        for query in queries:
            params = {"offered_by": "ocw", **query}
            resp = self.safe_request(
                self.MIT_API_BASE,
                params=params,
                timeout=15,
                source_name="MIT OCW",
                headers={"Accept": "application/json"},
            )
            if resp is None:
                continue

            try:
                results = resp.json().get("results", [])
            except Exception:
                continue

            for item in results:
                course_id = str(item.get("id") or "")
                if not course_id or course_id in seen_ids:
                    continue
                seen_ids.add(course_id)

                title = str(item.get("title") or "").strip()
                description = str(item.get("description") or "").strip()
                if not title:
                    continue

                course_url = str(item.get("url") or "").strip()
                if course_url and not course_url.startswith("http"):
                    course_url = urljoin("https://ocw.mit.edu", course_url)

                runs = item.get("runs") or []
                level = "master"
                if runs and isinstance(runs, list):
                    first = runs[0] if isinstance(runs[0], dict) else {}
                    levels = first.get("level") or []
                    if (
                        levels
                        and isinstance(levels, list)
                        and isinstance(levels[0], dict)
                    ):
                        code = str(levels[0].get("code") or "").lower()
                        if code == "undergraduate":
                            level = "bachelor"
                        elif code == "graduate":
                            level = "master"

                metadata = self._build_course_metadata(
                    title=title,
                    description=description,
                    source_url=course_url,
                    page_html="",
                )
                self._create_course(
                    title=title,
                    description=description,
                    institution=institution,
                    website=course_url,
                    field=metadata["field"],
                    level=level,
                    instructor=metadata["instructor"],
                    duration=metadata["duration"],
                    platform="mit",
                    enrollment_url=metadata["enrollment_url"] or course_url,
                    thumbnail_url=metadata["thumbnail_url"],
                    is_free=True,
                    price=None,
                    certificate_available=metadata["certificate_available"],
                    start_date=metadata["start_date"],
                    source_url=course_url,
                    source_name="MIT OpenCourseWare",
                )

    def _scrape_fast_ai(self):
        institution = self._ensure_institution(
            name="fast.ai",
            website="https://course.fast.ai",
            country_name="United States",
            country_code="US",
            inst_type="Other",
        )
        if institution is None:
            return

        for listing_url in self.FASTAI_URLS:
            resp = self.safe_request(listing_url, timeout=10, source_name="fast.ai")
            if resp is None:
                continue

            cards = self._extract_catalog_cards(resp.text, listing_url)
            for card in cards:
                title = card.get("title", "")
                if not title:
                    continue
                if "fast" not in title.lower() and not self._is_ai_nlp_related(
                    f"{title} {card.get('description', '')}"
                ):
                    continue

                url = card.get("url") or listing_url
                metadata = self._build_course_metadata(
                    title=title,
                    description=card.get("description", ""),
                    source_url=url,
                    page_html=card.get("raw_html", ""),
                    instructor_hint="Jeremy Howard, Rachel Thomas",
                    duration_hint=card.get("duration", ""),
                )
                self._create_course(
                    title=title,
                    description=card.get("description", ""),
                    institution=institution,
                    website=url,
                    field=metadata["field"],
                    level=metadata["level"],
                    instructor=metadata["instructor"] or "Jeremy Howard, Rachel Thomas",
                    duration=metadata["duration"],
                    platform="other",
                    enrollment_url=metadata["enrollment_url"] or url,
                    thumbnail_url=metadata["thumbnail_url"],
                    is_free=True,
                    price=None,
                    certificate_available=metadata["certificate_available"],
                    start_date=metadata["start_date"],
                    source_url=url,
                    source_name="fast.ai",
                )

    def _scrape_huggingface_course(self):
        institution = self._ensure_institution(
            name="Hugging Face",
            website="https://huggingface.co/learn",
            country_name="United States",
            country_code="US",
            inst_type="Other",
        )
        if institution is None:
            return

        resp = self.safe_request(
            self.HF_LEARN_URL, timeout=10, source_name="Hugging Face"
        )
        if resp is None:
            return

        cards = self._extract_catalog_cards(resp.text, self.HF_LEARN_URL)
        if not cards:
            cards = self._extract_list_items_as_courses(resp.text, self.HF_LEARN_URL)

        for card in cards:
            title = card.get("title", "")
            if not title:
                continue
            if not self._is_ai_nlp_related(f"{title} {card.get('description', '')}"):
                continue

            url = card.get("url") or self.HF_LEARN_URL
            metadata = self._build_course_metadata(
                title=title,
                description=card.get("description", ""),
                source_url=url,
                page_html=card.get("raw_html", ""),
            )
            self._create_course(
                title=title,
                description=card.get("description", ""),
                institution=institution,
                website=url,
                field=metadata["field"],
                level=metadata["level"],
                instructor=metadata["instructor"] or "Hugging Face Team",
                duration=metadata["duration"],
                platform="other",
                enrollment_url=metadata["enrollment_url"] or url,
                thumbnail_url=metadata["thumbnail_url"],
                is_free=True,
                price=None,
                certificate_available=metadata["certificate_available"],
                start_date=metadata["start_date"],
                source_url=url,
                source_name="Hugging Face Learn",
            )

    def _scrape_deeplearning_ai(self):
        institution = self._ensure_institution(
            name="DeepLearning.AI",
            website="https://www.deeplearning.ai",
            country_name="United States",
            country_code="US",
            inst_type="Other",
        )
        if institution is None:
            return

        resp = self.safe_request(
            self.DEEPLEARNING_AI_COURSES,
            timeout=10,
            source_name="DeepLearning.AI",
        )
        if resp is None:
            return

        cards = self._extract_catalog_cards(resp.text, self.DEEPLEARNING_AI_COURSES)
        for card in cards:
            title = card.get("title", "")
            if not title:
                continue
            if not self._is_ai_nlp_related(f"{title} {card.get('description', '')}"):
                continue

            url = card.get("url") or self.DEEPLEARNING_AI_COURSES
            metadata = self._build_course_metadata(
                title=title,
                description=card.get("description", ""),
                source_url=url,
                page_html=card.get("raw_html", ""),
            )
            self._create_course(
                title=title,
                description=card.get("description", ""),
                institution=institution,
                website=url,
                field=metadata["field"],
                level=metadata["level"],
                instructor=metadata["instructor"],
                duration=metadata["duration"],
                platform="other",
                enrollment_url=metadata["enrollment_url"] or url,
                thumbnail_url=metadata["thumbnail_url"],
                is_free=metadata["is_free"],
                price=metadata["price"],
                certificate_available=metadata["certificate_available"],
                start_date=metadata["start_date"],
                source_url=url,
                source_name="DeepLearning.AI",
            )

    def _import_curated_courses(self):
        for item in CURATED_COURSES:
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            website = str(item.get("website") or "").strip()
            if not title:
                continue

            institution = self._ensure_institution(
                name=item.get("institution_name") or "Unknown Institution",
                website=website,
                country_name=item.get("institution_country") or "International",
                country_code=(item.get("institution_country") or "XX")[:2].upper(),
                city=item.get("institution_city") or "",
                inst_type="University",
            )
            if institution is None:
                continue

            metadata = self._build_course_metadata(
                title=title,
                description=description,
                source_url=website,
                page_html="",
                instructor_hint=item.get("instructor", ""),
                duration_hint=item.get("duration", ""),
            )

            self._create_course(
                title=title,
                description=description,
                institution=institution,
                website=website,
                field=item.get("field") or metadata["field"],
                level=item.get("level") or metadata["level"],
                prerequisites=item.get("prerequisites") or "",
                syllabus=item.get("syllabus") or "",
                instructor=item.get("instructor") or metadata["instructor"],
                duration=item.get("duration") or metadata["duration"],
                platform=self._normalize_platform(
                    item.get("platform") or self._infer_platform(website)
                ),
                enrollment_url=item.get("enrollment_url")
                or metadata["enrollment_url"]
                or website,
                thumbnail_url=item.get("thumbnail_url") or metadata["thumbnail_url"],
                is_free=bool(item.get("is_free", metadata["is_free"])),
                price=self._parse_price(item.get("price")) or metadata["price"],
                certificate_available=bool(
                    item.get("certificate_available", metadata["certificate_available"])
                ),
                start_date=self.parse_date(item.get("start_date"))
                if item.get("start_date")
                else metadata["start_date"],
                source_url=item.get("source_url") or website,
                source_name=item.get("source_name") or "Curated Courses",
            )

    def _import_youtube_fixture_playlists(self):
        institution = self._ensure_institution(
            name="YouTube Educational Content",
            website="https://www.youtube.com",
            country_name="International",
            country_code="XX",
            inst_type="Other",
        )
        if institution is None:
            return

        for item in YOUTUBE_PLAYLISTS:
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            link = str(item.get("link") or "").strip()
            if not title or not link:
                continue

            metadata = self._build_course_metadata(
                title=title,
                description=description,
                source_url=link,
                page_html="",
                instructor_hint=item.get("instructor", ""),
                duration_hint=item.get("duration", ""),
            )
            self._create_course(
                title=title,
                description=description,
                institution=institution,
                website=link,
                field=metadata["field"],
                level=item.get("level") or metadata["level"],
                instructor=item.get("instructor") or metadata["instructor"],
                duration=item.get("duration") or metadata["duration"],
                platform="youtube",
                enrollment_url=link,
                thumbnail_url=item.get("thumbnail_url") or metadata["thumbnail_url"],
                is_free=True,
                price=None,
                certificate_available=bool(
                    item.get("certificate_available", metadata["certificate_available"])
                ),
                start_date=metadata["start_date"],
                source_url=link,
                source_name="YouTube",
            )

    # ------------------------------------------------------------------
    # YouTube playlist search (API if available, fallback scraping)
    # ------------------------------------------------------------------

    def _scrape_youtube_playlists(self, terms: list[str], source_name: str):
        institution = self._ensure_institution(
            name="YouTube Educational Content",
            website="https://www.youtube.com",
            country_name="International",
            country_code="XX",
            inst_type="Other",
        )
        if institution is None:
            return

        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        seen_playlists: set[str] = set()

        if api_key:
            self._scrape_youtube_playlists_api(
                terms, api_key, institution, source_name, seen_playlists
            )
        else:
            self._scrape_youtube_playlists_html(
                terms, institution, source_name, seen_playlists
            )

    def _scrape_youtube_playlists_api(
        self, terms, api_key, institution, source_name, seen_playlists
    ):
        search_endpoint = "https://www.googleapis.com/youtube/v3/search"
        playlist_endpoint = "https://www.googleapis.com/youtube/v3/playlists"

        for term in terms:
            params = {
                "part": "snippet",
                "q": term,
                "type": "playlist",
                "maxResults": 10,
                "key": api_key,
            }
            resp = self.safe_request(
                search_endpoint, params=params, timeout=15, source_name="YouTube API"
            )
            if resp is None:
                continue

            try:
                items = resp.json().get("items", [])
            except Exception:
                continue

            for item in items:
                snippet = item.get("snippet") or {}
                playlist_id = str(
                    (item.get("id") or {}).get("playlistId") or ""
                ).strip()
                if not playlist_id:
                    continue

                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                key = playlist_url.rstrip("/")
                if key in seen_playlists:
                    continue
                seen_playlists.add(key)

                detail_resp = self.safe_request(
                    playlist_endpoint,
                    params={
                        "part": "snippet,contentDetails",
                        "id": playlist_id,
                        "key": api_key,
                    },
                    timeout=15,
                    source_name="YouTube API",
                )
                item_count = None
                thumbnail_url = ""
                if detail_resp is not None:
                    try:
                        payload = detail_resp.json().get("items", [])
                        if payload:
                            detail = payload[0]
                            item_count = (detail.get("contentDetails") or {}).get(
                                "itemCount"
                            )
                            thumbs = (detail.get("snippet") or {}).get(
                                "thumbnails"
                            ) or {}
                            thumbnail_url = (
                                (thumbs.get("high") or {}).get("url")
                                or (thumbs.get("medium") or {}).get("url")
                                or (thumbs.get("default") or {}).get("url")
                                or ""
                            )
                    except Exception:
                        pass

                title = str(snippet.get("title") or "").strip()
                channel = str(snippet.get("channelTitle") or "").strip()
                description = str(snippet.get("description") or "").strip()
                if not self._is_ai_nlp_related(f"{title} {description} {term}"):
                    continue

                duration = f"{item_count} videos" if item_count else ""
                metadata = self._build_course_metadata(
                    title=title,
                    description=description,
                    source_url=playlist_url,
                    page_html="",
                    instructor_hint=channel,
                    duration_hint=duration,
                )
                self._create_course(
                    title=title,
                    description=description,
                    institution=institution,
                    website=playlist_url,
                    field=metadata["field"],
                    level=metadata["level"],
                    instructor=channel or metadata["instructor"],
                    duration=duration or metadata["duration"],
                    platform="youtube",
                    enrollment_url=playlist_url,
                    thumbnail_url=thumbnail_url or metadata["thumbnail_url"],
                    is_free=True,
                    price=None,
                    certificate_available=metadata["certificate_available"],
                    start_date=metadata["start_date"],
                    source_url=playlist_url,
                    source_name=f"{source_name} ({term})",
                )

    def _scrape_youtube_playlists_html(
        self, terms, institution, source_name, seen_playlists
    ):
        for term in terms:
            # "sp=EgIQAw%253D%253D" is playlist filter in YouTube search.
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(term)}&sp=EgIQAw%253D%253D"
            resp = self.safe_request(search_url, timeout=10, source_name="YouTube")
            if resp is None:
                continue

            html = resp.text or ""
            playlist_ids = set(re.findall(r'"playlistId":"([^"]+)"', html))
            if not playlist_ids:
                playlist_ids = set(
                    re.findall(r"/playlist\?list=([A-Za-z0-9_-]{10,})", html)
                )

            for playlist_id in list(playlist_ids)[:10]:
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                key = playlist_url.rstrip("/")
                if key in seen_playlists:
                    continue
                seen_playlists.add(key)

                title = self._extract_playlist_title_from_html(html, playlist_id)
                channel = self._extract_playlist_channel_from_html(html, playlist_id)
                if not title:
                    title = f"YouTube Playlist {playlist_id}"

                if not self._is_ai_nlp_related(f"{title} {term} {channel}"):
                    continue

                self._create_course(
                    title=title,
                    description=f"Playlist discovered for query: {term}",
                    institution=institution,
                    website=playlist_url,
                    field=self._detect_field(f"{title} {term}"),
                    level=self._detect_level(title),
                    instructor=channel,
                    duration="",
                    platform="youtube",
                    enrollment_url=playlist_url,
                    thumbnail_url="",
                    is_free=True,
                    price=None,
                    certificate_available=False,
                    start_date=None,
                    source_url=playlist_url,
                    source_name=f"{source_name} ({term})",
                )

    @staticmethod
    def _extract_playlist_title_from_html(html: str, playlist_id: str) -> str:
        pattern = re.compile(
            rf'"playlistId":"{re.escape(playlist_id)}".*?"title":\{{"simpleText":"([^"]+)"\}}',
            re.S,
        )
        match = pattern.search(html)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_playlist_channel_from_html(html: str, playlist_id: str) -> str:
        pattern = re.compile(
            rf'"playlistId":"{re.escape(playlist_id)}".*?"longBylineText":\{{.*?"text":"([^"]+)"',
            re.S,
        )
        match = pattern.search(html)
        if match:
            return match.group(1).strip()
        return ""

    # ------------------------------------------------------------------
    # Shared parsing helpers
    # ------------------------------------------------------------------

    def _extract_catalog_cards(self, html: str, page_url: str) -> list[dict]:
        soup = BeautifulSoup(html or "", "html.parser")
        cards = []
        seen: set[str] = set()

        selectors = [
            "article",
            ".course",
            ".course-card",
            ".card",
            "li",
            "a",
        ]

        for selector in selectors:
            for node in soup.select(selector):
                anchor = node if node.name == "a" else node.find("a", href=True)
                if not anchor:
                    continue

                href = (anchor.get("href") or "").strip()
                if not href or href.startswith("#"):
                    continue
                url = urljoin(page_url, href)
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"}:
                    continue

                key = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}".rstrip(
                    "/"
                )
                if key in seen:
                    continue
                seen.add(key)

                title = self.clean_text(
                    anchor.get_text(" ", strip=True)
                    or (
                        node.find(["h1", "h2", "h3", "h4"]).get_text(" ", strip=True)
                        if node.find(["h1", "h2", "h3", "h4"])
                        else ""
                    )
                )
                if not title or len(title) < 3:
                    continue

                description = ""
                desc_node = node.find(["p", "small", "span"]) or node
                if desc_node:
                    description = self.clean_text(desc_node.get_text(" ", strip=True))
                description = description[:1500]

                cards.append(
                    {
                        "title": title[:300],
                        "description": description,
                        "url": url,
                        "raw_html": str(node)[:6000],
                    }
                )

            if len(cards) >= 50:
                break

        return cards[:100]

    def _extract_list_items_as_courses(self, html: str, page_url: str) -> list[dict]:
        soup = BeautifulSoup(html or "", "html.parser")
        courses = []
        for li in soup.select("li"):
            text = self.clean_text(li.get_text(" ", strip=True))
            if len(text) < 10:
                continue
            if not self._is_ai_nlp_related(text):
                continue

            anchor = li.find("a", href=True)
            url = urljoin(page_url, anchor.get("href")) if anchor else page_url
            courses.append(
                {
                    "title": text[:220],
                    "description": text[:1200],
                    "url": url,
                    "raw_html": str(li)[:5000],
                }
            )
        return courses[:40]

    def _build_course_metadata(
        self,
        *,
        title: str,
        description: str,
        source_url: str,
        page_html: str,
        instructor_hint: str = "",
        duration_hint: str = "",
    ) -> dict:
        text_blob = self.clean_text(f"{title} {description} {page_html}")

        instructor = instructor_hint or self._extract_instructor_text(text_blob)
        duration = duration_hint or self._extract_duration_text(text_blob)
        platform = self._normalize_platform(self._infer_platform(source_url))
        enrollment_url = self._extract_enrollment_url(page_html, source_url)
        thumbnail_url = self._extract_thumbnail_url(page_html, source_url)
        is_free = self._detect_is_free(text_blob)
        price = None if is_free else self._extract_price(text_blob)
        certificate_available = self._detect_certificate(text_blob)
        start_date = self._extract_start_date(text_blob)

        return {
            "field": self._detect_field(text_blob),
            "level": self._detect_level(text_blob),
            "instructor": instructor,
            "duration": duration,
            "platform": platform,
            "enrollment_url": enrollment_url,
            "thumbnail_url": thumbnail_url,
            "is_free": is_free,
            "price": price,
            "certificate_available": certificate_available,
            "start_date": start_date,
        }

    def _detect_field(self, text: str) -> str:
        haystack = (text or "").lower()
        for key, value in FIELD_MAP.items():
            if key in haystack:
                return value
        return "nlp"

    def _detect_level(self, text: str) -> str:
        haystack = (text or "").lower()
        for hint, level in LEVEL_HINTS.items():
            if hint in haystack:
                return level
        return "bachelor"

    def _extract_instructor_text(self, text: str) -> str:
        patterns = [
            r"(?:instructor|teacher|taught by|professor|lecturer)\s*[:\-]?\s*([^\n\r\|]{3,120})",
            r"(?:formateur|anim(?:e|é) par|enseignant)\s*[:\-]?\s*([^\n\r\|]{3,120})",
            r"(?:المدرس|المحاضر|يقدمه|تقديم)\s*[:\-]?\s*([^\n\r\|]{3,120})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text or "", re.I)
            if match:
                return self.clean_text(match.group(1))[:255]
        return ""

    def _extract_duration_text(self, text: str) -> str:
        match = DURATION_PATTERN.search(text or "")
        if match:
            return self.clean_text(match.group(1))[:100]
        return ""

    def _extract_enrollment_url(self, html: str, base_url: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            label = self.clean_text(anchor.get_text(" ", strip=True)).lower()
            if any(
                token in label
                for token in (
                    "enroll",
                    "register",
                    "join",
                    "s'inscrire",
                    "inscription",
                    "سجل",
                    "التحاق",
                )
            ):
                return urljoin(base_url, anchor.get("href", ""))
        return ""

    def _extract_thumbnail_url(self, html: str, base_url: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        og = soup.select_one("meta[property='og:image']")
        if og and og.get("content"):
            return urljoin(base_url, og.get("content"))

        img = soup.select_one("img[src]")
        if img and img.get("src"):
            return urljoin(base_url, img.get("src"))
        return ""

    def _detect_is_free(self, text: str) -> bool:
        haystack = (text or "").lower()
        if any(
            token in haystack
            for token in (
                "free",
                "gratuit",
                "مجاني",
                "price: 0",
                "0 usd",
                "0 eur",
                "0 dzd",
            )
        ):
            return True
        # If we explicitly detect a non-zero price, not free.
        price = self._extract_price(haystack)
        return price is None

    def _extract_price(self, text: str):
        match = PRICE_PATTERN.search(text or "")
        if not match:
            return None
        return self._parse_price(match.group(0))

    def _detect_certificate(self, text: str) -> bool:
        haystack = (text or "").lower()
        return any(
            token in haystack
            for token in ("certificate", "certification", "attestation", "شهادة")
        )

    def _extract_start_date(self, text: str):
        match = START_DATE_PATTERN.search(text or "")
        if not match:
            return None
        return self.parse_date(match.group(1))

    def _infer_platform(self, url: str) -> str:
        link = (url or "").lower()
        if "coursera" in link:
            return "coursera"
        if "youtube" in link or "youtu.be" in link:
            return "youtube"
        if "mit.edu" in link:
            return "mit"
        if "edx" in link:
            return "edx"
        if any(key in link for key in ("univ-", "edu.dz", "elearning.")):
            return "university"
        return "other"

    @staticmethod
    def _normalize_platform(value: str) -> str:
        value = (value or "other").lower().strip()
        if value in {"coursera", "youtube", "mit", "edx", "university", "other"}:
            return value
        return "other"

    @staticmethod
    def _parse_price(raw_price):
        if raw_price in (None, "", "free", "Free"):
            return None
        try:
            cleaned = re.sub(r"[^0-9.]", "", str(raw_price))
            if not cleaned:
                return None
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def _is_ai_nlp_related(self, text: str) -> bool:
        haystack = (text or "").lower()
        return any(keyword in haystack for keyword in self.AI_NLP_KEYWORDS)

    def _ensure_institution(
        self,
        *,
        name: str,
        website: str,
        country_name: str,
        country_code: str,
        city: str = "",
        inst_type: str = "University",
    ):
        country = self.get_or_create_country(country_name, country_code[:2].upper())
        return self.get_or_create_institution(
            name,
            country=country,
            city=city,
            website=website,
            inst_type=inst_type,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _create_course(
        self,
        *,
        title,
        description,
        institution,
        website="",
        field="nlp",
        level="bachelor",
        prerequisites="",
        syllabus="",
        end_date=None,
        last_updated=None,
        instructor="",
        duration="",
        platform="other",
        enrollment_url="",
        thumbnail_url="",
        is_free=True,
        price=None,
        certificate_available=False,
        start_date=None,
        source_url="",
        source_name="",
    ):
        from resources.models import Course

        if not title:
            return

        if not self.is_course_still_available(
            end_date=end_date,
            last_updated=last_updated,
            max_age_days=730,
        ):
            self.items_skipped += 1
            return

        source_url = source_url or website
        source_name = source_name or "unknown"

        media_seed = {
            "title_en": title,
            "source_url": source_url,
            "course_url": website,
            "thumbnail_url": thumbnail_url,
            "syllabus_file_url": "",
        }
        media_seed = self._download_media(media_seed, "courses")

        is_duplicate, _ = self._check_duplicate_policy(
            "courses",
            {
                "title_en": title,
                "description_en": description,
                "course_url": website,
                "access_link": website,
                "instructor": instructor,
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return

        import datetime

        current_year = datetime.datetime.now().year
        academic_year = f"{current_year}-{current_year + 1}"

        item_dict = {
            "title_en": title,
            "title_ar": title,
            "description_en": description,
            "description_ar": description,
            "field_of_study": field,
            "academic_level": level,
            "teaching_language": "arabic"
            if self.detect_language(description) == "ar"
            else "english",
            "course_url": website,
            "keywords": ["nlp", "ai", "machine learning"],
            "prerequisites": prerequisites,
            "syllabus": syllabus,
            "academic_year": academic_year,
            "syllabus_file_url": "",
            "instructor": instructor,
            "duration": duration,
            "platform": self._normalize_platform(platform),
            "enrollment_url": enrollment_url,
            "thumbnail_url": thumbnail_url,
            "is_free": bool(is_free),
            "price": self._parse_price(price) if isinstance(price, str) else price,
            "certificate_available": bool(certificate_available),
            "start_date": start_date,
            "source_url": source_url,
            "source_name": source_name,
            "image_local_path": media_seed.get("image_local_path") or "",
            "image_content_file": media_seed.get("image_content_file"),
            "pdf_local_path": media_seed.get("pdf_local_path") or "",
            "pdf_content_file": media_seed.get("pdf_content_file"),
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

        language = (
            "ar"
            if str(item_dict.get("teaching_language", "english")).lower() == "arabic"
            else "en"
        )

        try:
            course = Course.objects.create(
                title=item_dict.get("title_en", "")[:300],
                title_en=item_dict.get("title_en", "")[:300],
                title_ar=item_dict.get("title_ar", "")[:300],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                field=item_dict.get("field_of_study", "nlp"),
                academic_level=item_dict.get("academic_level", "bachelor"),
                teacher=self.get_system_user(),
                institution=institution,
                academic_year=item_dict.get("academic_year", academic_year),
                access_link=item_dict.get("course_url", ""),
                language=language,
                keywords=", ".join(item_dict.get("keywords", [])),
                prerequisites=item_dict.get("prerequisites", ""),
                syllabus=item_dict.get("syllabus", ""),
                instructor=item_dict.get("instructor") or None,
                duration=item_dict.get("duration") or None,
                platform=item_dict.get("platform", "other"),
                enrollment_url=item_dict.get("enrollment_url") or None,
                is_free=bool(item_dict.get("is_free", True)),
                price=item_dict.get("price"),
                certificate_available=bool(
                    item_dict.get("certificate_available", False)
                ),
                start_date=item_dict.get("start_date"),
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
                author=self.get_system_user(),
                approval_status="pending",
            )

            pdf_local_path = item_dict.get("pdf_local_path") or ""
            if pdf_local_path:
                try:
                    attach_file_to_model(
                        course,
                        "uploaded_file",
                        item_dict.get("pdf_content_file"),
                        pdf_local_path,
                    )
                except Exception:
                    pass

            image_local_path = item_dict.get("image_local_path") or ""
            if image_local_path:
                try:
                    attach_file_to_model(
                        course,
                        "thumbnail",
                        item_dict.get("image_content_file"),
                        image_local_path,
                    )
                except Exception:
                    pass

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 100),
                    "institution": getattr(institution, "name_en", ""),
                    "level": item_dict.get("academic_level", level),
                    "url": item_dict.get("course_url", website),
                    "source_name": item_dict.get("source_name", ""),
                }
            )
        except Exception as exc:
            self.errors.append(
                f"Failed to create course '{self.truncate(title, 60)}': {exc}"
            )
            logger.error(
                "Failed to create course %s: %s", self.truncate(title, 60), exc
            )
