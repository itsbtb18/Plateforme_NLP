"""
Tiered institutions scraper with Algerian-first priority policy.

Priority:
1) Algerian institutions
2) North African / Arabic institutions
3) African institutions
4) Global top NLP labs
"""

import json
import logging
import os
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraping.enrichment_engine import enrich_scraped_item
from scraping.field_mapping import calculate_completeness_score
from scraping.file_downloader import attach_file_to_model

from .base import BaseScraper

logger = logging.getLogger(__name__)


def _load_curated_institutions():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "fixtures",
        "curated_institutions.json",
    )
    try:
        with open(fixture_path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


_FIXTURE = _load_curated_institutions()

TYPE_MAP = {
    # Requested mapping from ROR type → internal semantic type.
    "education": "university",
    "nonprofit": "research_centre",
    "facility": "lab",
    "government": "research_centre",
    "company": "industry_lab",
}

MODEL_TYPE_MAP = {
    "university": "University",
    "research_centre": "Research Center",
    "lab": "Research Center",
    "industry_lab": "Other",
}

DIRECTOR_PATTERNS = [
    r"(?:director|head|dean)\s*[:\-]?\s*([^\n\r\|<]{3,120})",
    r"(?:directeur|responsable)\s*[:\-]?\s*([^\n\r\|<]{3,120})",
    r"(?:المدير|رئيس(?:ة)?\s*(?:المخبر|المركز|القسم))\s*[:\-]?\s*([^\n\r\|<]{3,120})",
]

YEAR_PATTERNS = [
    r"(?:founded|established|since)\s*(?:in)?\s*(19\d{2}|20\d{2})",
    r"(?:fond(?:e|é)e?|creation|cr(?:e|é)ation)\s*(?:en)?\s*(19\d{2}|20\d{2})",
    r"(?:ت(?:أسس|أسست)|أنشئت|منذ)\s*(?:عام)?\s*(19\d{2}|20\d{2})",
]

SOCIAL_DOMAINS = {
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "github.com": "github",
    "facebook.com": "facebook",
    "youtube.com": "youtube",
}

ALGERIAN_LAB_SCAN_UNIVERSITIES = [
    "https://www.univ-alger.dz",
    "https://www.esi.dz",
    "https://www.usthb.dz",
    "https://www.umc.edu.dz",
    "https://www.univ-oran1.dz",
]

LAB_PATHS = ["/laboratoires", "/labo", "/labs"]

TOP_GLOBAL_LABS = [
    {
        "name": "Stanford NLP Group",
        "website": "https://nlp.stanford.edu",
        "country_name": "United States",
        "country_code": "US",
        "city": "Stanford",
    },
    {
        "name": "MIT CSAIL",
        "website": "https://www.csail.mit.edu",
        "country_name": "United States",
        "country_code": "US",
        "city": "Cambridge",
    },
    {
        "name": "CMU Language Technologies Institute",
        "website": "https://www.lti.cs.cmu.edu",
        "country_name": "United States",
        "country_code": "US",
        "city": "Pittsburgh",
    },
    {
        "name": "Edinburgh NLP",
        "website": "https://nlp.inf.ed.ac.uk",
        "country_name": "United Kingdom",
        "country_code": "GB",
        "city": "Edinburgh",
    },
    {
        "name": "Johns Hopkins CLSP",
        "website": "https://www.clsp.jhu.edu",
        "country_name": "United States",
        "country_code": "US",
        "city": "Baltimore",
    },
    {
        "name": "NYU Abu Dhabi CAMeL Lab",
        "website": "https://nyuad.nyu.edu/en/research/faculty-labs-and-projects/camel-lab.html",
        "country_name": "United Arab Emirates",
        "country_code": "AE",
        "city": "Abu Dhabi",
    },
    {
        "name": "Qatar Computing Research Institute",
        "website": "https://www.hbku.edu.qa/en/qcri",
        "country_name": "Qatar",
        "country_code": "QA",
        "city": "Doha",
    },
    {
        "name": "Mohamed bin Zayed University of Artificial Intelligence",
        "website": "https://mbzuai.ac.ae",
        "country_name": "United Arab Emirates",
        "country_code": "AE",
        "city": "Abu Dhabi",
    },
]

TIER_1_RSS_SOURCES = [
    {
        "base_url": "https://www.cerist.dz",
        "source_name": "CERIST",
        "country_name": "Algeria",
        "country_code": "DZ",
        "semantic_type": "research_centre",
    },
    {
        "base_url": "https://www.cdta.dz",
        "source_name": "CDTA",
        "country_name": "Algeria",
        "country_code": "DZ",
        "semantic_type": "research_centre",
    },
    {
        "base_url": "https://www.esi.dz",
        "source_name": "ESI",
        "country_name": "Algeria",
        "country_code": "DZ",
        "semantic_type": "university",
    },
]

TIER_2_RSS_SOURCES = [
    {
        "base_url": "https://www.hbku.edu.qa/en/qcri",
        "source_name": "QCRI",
        "country_name": "Qatar",
        "country_code": "QA",
        "semantic_type": "research_centre",
    },
    {
        "base_url": "https://nyuad.nyu.edu",
        "source_name": "NYU Abu Dhabi",
        "country_name": "United Arab Emirates",
        "country_code": "AE",
        "semantic_type": "research_centre",
    },
    {
        "base_url": "https://mbzuai.ac.ae",
        "source_name": "MBZUAI",
        "country_name": "United Arab Emirates",
        "country_code": "AE",
        "semantic_type": "university",
    },
]

TIER_3_RSS_SOURCES = [
    {
        "base_url": "https://www.masakhane.io",
        "source_name": "Masakhane",
        "country_name": "International",
        "country_code": "XX",
        "semantic_type": "research_centre",
    }
]

TIER_4_RSS_SOURCES = [
    {
        "base_url": "https://nlp.stanford.edu",
        "source_name": "Stanford NLP",
        "country_name": "United States",
        "country_code": "US",
        "semantic_type": "lab",
    },
    {
        "base_url": "https://www.lti.cs.cmu.edu",
        "source_name": "CMU LTI",
        "country_name": "United States",
        "country_code": "US",
        "semantic_type": "lab",
    },
]


class InstitutionScraper(BaseScraper):
    """Scrape institutions with deterministic ROR-based dedup inputs."""

    name = "NLP Research Institutions"
    category = "institutions"

    ROR_BASE = "https://api.ror.org/organizations"
    OPENALEX_INSTITUTIONS = "https://api.openalex.org/institutions"
    OPENALEX_WORKS = "https://api.openalex.org/works"

    def run(self) -> dict:
        """Run the institutions scraper with source-level checkpoint resume.

        Returns:
            dict: Standard scraper run summary.

        Raises:
            Exception: Re-raises failures after logging checkpoint diagnostics.
        """
        from scraping.checkpoint import ScraperCheckpoint

        run_id = getattr(self, "_current_run_id", "unknown")
        cp = ScraperCheckpoint("institutions", run_id)

        if cp.is_resuming():
            logger.info(
                "scraper_resuming_from_checkpoint",
                extra=cp.get_summary(),
            )

        self._checkpoint = cp

        logger.info(
            "scraper_run_config",
            extra={
                "category": self.category,
                "source_name": self.name,
                "media_download_enabled": self._is_download_enabled(),
            },
        )
        try:
            result = super().run()
            cp.clear()
            return result
        except Exception as exc:
            logger.error(
                "scraper_interrupted_checkpoint_saved",
                extra={
                    "run_id": run_id,
                    "error": str(exc),
                    "summary": cp.get_summary(),
                },
            )
            raise

    def scrape(self):
        """Execute institution source tiers from local to global scope."""
        self._scrape_tier_1_algeria()
        self._scrape_tier_2_north_africa_arabic()
        self._scrape_tier_3_africa()
        self._scrape_tier_4_global()

    # ------------------------------------------------------------------
    # Tier 1 — Algerian institutions
    # ------------------------------------------------------------------

    def _scrape_tier_1_algeria(self):
        cp = getattr(self, "_checkpoint", None)
        methods = [
            (
                "tier1_rss",
                lambda: self._scrape_rss_institution_sources(TIER_1_RSS_SOURCES),
            ),
            (
                "ror_algeria",
                lambda: self._sync_ror_country("DZ", "Tier1 ROR Algeria"),
            ),
            ("cerist", self._add_cerist_hardcoded),
            ("cdta", self._scrape_cdta),
            ("algerian_ai_labs", self._scan_algerian_ai_labs),
        ]
        for source_name, method in methods:
            if cp and cp.is_source_done(source_name):
                logger.info(
                    "source_skipped_already_done",
                    extra={"source": source_name},
                )
                continue
            try:
                method()
                if cp:
                    cp.mark_source_done(source_name)
            except Exception as exc:
                logger.error(
                    "source_scrape_failed",
                    extra={"source": source_name, "error": str(exc)},
                )

    def _add_cerist_hardcoded(self):
        dz = self.get_or_create_country("Algeria", "DZ", name_ar="الجزائر")
        description_en = (
            "CERIST is Algeria's national research center for scientific and technical "
            "information, with active programs in information science, NLP, and digital libraries."
        )
        description_ar = (
            "مركز البحث في الإعلام العلمي والتقني هو مركز بحث وطني جزائري نشط في علوم "
            "المعلومات ومعالجة اللغة الطبيعية والمكتبات الرقمية."
        )

        self._create_institution_item(
            name_en="Centre de Recherche sur l'Information Scientifique et Technique",
            name_ar="مركز البحث في الإعلام العلمي والتقني",
            acronym="CERIST",
            ror_id="",
            semantic_type="research_centre",
            country=dz,
            city_en="Algiers",
            city_ar="الجزائر",
            description_en=description_en,
            description_ar=description_ar,
            website="https://www.cerist.dz",
            source_url="https://www.cerist.dz",
            source_name="Tier1 CERIST Hardcoded",
            research_specialties=["information science", "NLP", "digital libraries"],
            founding_year=None,
            director=None,
            affiliated_researchers_count=None,
            notable_publications=None,
            social_links=None,
        )

    def _scrape_cdta(self):
        base_url = "https://www.cdta.dz"
        dz = self.get_or_create_country("Algeria", "DZ", name_ar="الجزائر")

        about_urls = [
            base_url,
            urljoin(base_url + "/", "about"),
            urljoin(base_url + "/", "a-propos"),
            urljoin(base_url + "/", "laboratoires"),
            urljoin(base_url + "/", "research"),
        ]
        page_bundles = self._fetch_website_bundle(about_urls, source_name="CDTA")
        merged_text = " ".join(bundle["text"] for bundle in page_bundles)

        director = self._extract_director(merged_text)
        founding_year = self._extract_founding_year(merged_text)
        social_links = self._extract_social_links(page_bundles)
        logo_url = self._extract_logo_url(page_bundles, base_url)
        research_areas = self._extract_research_areas(merged_text)

        description = (
            "CDTA (Centre de Developpement des Technologies Avancees) is an Algerian "
            "research center focused on AI, robotics, advanced systems, and language technologies."
        )
        if merged_text:
            description = self.truncate(self.clean_text(merged_text), 1800)

        self._create_institution_item(
            name_en="Centre de Developpement des Technologies Avancees",
            name_ar="مركز تطوير التكنولوجيات المتقدمة",
            acronym="CDTA",
            ror_id="",
            semantic_type="research_centre",
            country=dz,
            city_en="Algiers",
            city_ar="الجزائر",
            description_en=description,
            description_ar=description,
            website=base_url,
            source_url=base_url,
            source_name="Tier1 CDTA",
            research_specialties=research_areas,
            founding_year=founding_year,
            director=director,
            affiliated_researchers_count=None,
            notable_publications=None,
            social_links=social_links,
            logo_url=logo_url,
        )

    def _scan_algerian_ai_labs(self):
        dz = self.get_or_create_country("Algeria", "DZ", name_ar="الجزائر")

        for university in ALGERIAN_LAB_SCAN_UNIVERSITIES:
            domain = urlparse(university).netloc
            for path in LAB_PATHS:
                url = urljoin(university.rstrip("/") + "/", path.lstrip("/"))
                resp = self.safe_request(url, timeout=10, source_name=domain)
                if resp is None:
                    continue

                labs = self._extract_lab_cards(resp.text, url)
                for lab in labs:
                    title = lab.get("name", "")
                    if not title:
                        continue
                    if not self._looks_like_ai_lab(
                        f"{title} {lab.get('description', '')}"
                    ):
                        continue

                    director = self._extract_director(lab.get("description", ""))
                    founding_year = self._extract_founding_year(
                        lab.get("description", "")
                    )
                    social_links = self._extract_social_links(
                        [
                            {
                                "url": url,
                                "html": resp.text,
                                "text": lab.get("description", ""),
                            }
                        ]
                    )
                    logo_url = self._extract_logo_url(
                        [
                            {
                                "url": url,
                                "html": resp.text,
                                "text": lab.get("description", ""),
                            }
                        ],
                        url,
                    )

                    self._create_institution_item(
                        name_en=title,
                        name_ar=title,
                        acronym=lab.get("acronym", ""),
                        ror_id="",
                        semantic_type="lab",
                        country=dz,
                        city_en="",
                        city_ar="",
                        description_en=lab.get("description", "")
                        or f"Research lab at {domain}",
                        description_ar=lab.get("description", "")
                        or f"Research lab at {domain}",
                        website=lab.get("url") or url,
                        source_url=url,
                        source_name=f"Tier1 Algerian Lab Scan ({domain})",
                        research_specialties=self._extract_research_areas(
                            lab.get("description", "")
                        ),
                        founding_year=founding_year,
                        director=director,
                        affiliated_researchers_count=None,
                        notable_publications=None,
                        social_links=social_links,
                        logo_url=logo_url,
                    )

    # ------------------------------------------------------------------
    # Tier 2 — North African / Arabic ROR
    # ------------------------------------------------------------------

    def _scrape_tier_2_north_africa_arabic(self):
        cp = getattr(self, "_checkpoint", None)
        methods = [
            (
                "tier2_rss",
                lambda: self._scrape_rss_institution_sources(TIER_2_RSS_SOURCES),
            ),
            ("ror_ma", lambda: self._sync_ror_country("MA", "Tier2 ROR MA")),
            ("ror_tn", lambda: self._sync_ror_country("TN", "Tier2 ROR TN")),
            ("ror_eg", lambda: self._sync_ror_country("EG", "Tier2 ROR EG")),
            ("ror_ly", lambda: self._sync_ror_country("LY", "Tier2 ROR LY")),
            ("ror_sa", lambda: self._sync_ror_country("SA", "Tier2 ROR SA")),
            ("ror_ae", lambda: self._sync_ror_country("AE", "Tier2 ROR AE")),
            ("ror_qa", lambda: self._sync_ror_country("QA", "Tier2 ROR QA")),
            ("ror_kw", lambda: self._sync_ror_country("KW", "Tier2 ROR KW")),
            ("ror_bh", lambda: self._sync_ror_country("BH", "Tier2 ROR BH")),
            ("ror_om", lambda: self._sync_ror_country("OM", "Tier2 ROR OM")),
        ]
        for source_name, method in methods:
            if cp and cp.is_source_done(source_name):
                logger.info(
                    "source_skipped_already_done",
                    extra={"source": source_name},
                )
                continue
            try:
                method()
                if cp:
                    cp.mark_source_done(source_name)
            except Exception as exc:
                logger.error(
                    "source_scrape_failed",
                    extra={"source": source_name, "error": str(exc)},
                )

    # ------------------------------------------------------------------
    # Tier 3 — Africa (OpenAlex + Masakhane)
    # ------------------------------------------------------------------

    def _scrape_tier_3_africa(self):
        cp = getattr(self, "_checkpoint", None)
        methods = [
            (
                "tier3_rss",
                lambda: self._scrape_rss_institution_sources(TIER_3_RSS_SOURCES),
            ),
            ("openalex_africa", self._scrape_openalex_africa),
            ("masakhane_affiliations", self._import_masakhane_affiliations),
        ]
        for source_name, method in methods:
            if cp and cp.is_source_done(source_name):
                logger.info(
                    "source_skipped_already_done",
                    extra={"source": source_name},
                )
                continue
            try:
                method()
                if cp:
                    cp.mark_source_done(source_name)
            except Exception as exc:
                logger.error(
                    "source_scrape_failed",
                    extra={"source": source_name, "error": str(exc)},
                )

    def _scrape_openalex_africa(self):
        page = 1
        per_page = 100

        while True:
            resp = self.safe_request(
                self.OPENALEX_INSTITUTIONS,
                params={
                    "filter": "continent:africa",
                    "per_page": per_page,
                    "page": page,
                    "mailto": "platform@nlp-research.org",
                },
                timeout=20,
                source_name="OpenAlex Africa",
            )
            if resp is None:
                break

            try:
                data = resp.json()
            except Exception:
                break

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                works_count = int(item.get("works_count") or 0)
                if works_count <= 100:
                    continue

                self._process_openalex_item(item, source_name="Tier3 OpenAlex Africa")

            if len(results) < per_page:
                break
            page += 1
            if page > 40:
                # Safety cap.
                break

    def _import_masakhane_affiliations(self):
        labs = _FIXTURE.get("african_nlp_labs", [])
        for item in labs:
            blob = f"{item.get('name', '')} {item.get('description', '')}".lower()
            if "masakhane" not in blob and "african" not in blob:
                continue

            country = self.get_or_create_country(
                item.get("country_name", "International"),
                (item.get("country_code", "XX") or "XX")[:2].upper(),
            )
            self._create_institution_item(
                name_en=item.get("name", "Masakhane"),
                name_ar=item.get("name_ar", item.get("name", "Masakhane")),
                acronym=item.get("acronym", ""),
                ror_id=item.get("ror_id", ""),
                semantic_type="research_centre",
                country=country,
                city_en=item.get("city", ""),
                city_ar=item.get("city", ""),
                description_en=item.get("description", ""),
                description_ar=item.get("description", ""),
                website=item.get("website", ""),
                source_url=item.get("source_url") or item.get("website", ""),
                source_name=item.get("source_name") or "Tier3 Masakhane",
                research_specialties=self._extract_research_areas(
                    item.get("description", "")
                ),
                founding_year=self._extract_founding_year(item.get("description", "")),
                director=item.get("director"),
                affiliated_researchers_count=item.get("affiliated_researchers_count"),
                notable_publications=item.get("notable_publications"),
                social_links=item.get("social_links"),
                logo_url=item.get("logo_url", ""),
            )

    # ------------------------------------------------------------------
    # Tier 4 — Global top labs
    # ------------------------------------------------------------------

    def _scrape_tier_4_global(self):
        cp = getattr(self, "_checkpoint", None)
        methods = [
            (
                "tier4_rss",
                lambda: self._scrape_rss_institution_sources(TIER_4_RSS_SOURCES),
            )
        ]
        for lab in TOP_GLOBAL_LABS:
            lab_name = str(lab.get("name", "global_lab")).strip().lower()
            source_key = "top_lab_" + re.sub(r"[^a-z0-9]+", "_", lab_name).strip("_")
            methods.append((source_key, lambda item=lab: self._scrape_top_lab(item)))

        for source_name, method in methods:
            if cp and cp.is_source_done(source_name):
                logger.info(
                    "source_skipped_already_done",
                    extra={"source": source_name},
                )
                continue
            try:
                method()
                if cp:
                    cp.mark_source_done(source_name)
            except Exception as exc:
                logger.error(
                    "source_scrape_failed",
                    extra={"source": source_name, "error": str(exc)},
                )

    def _scrape_rss_institution_sources(self, sources: list[dict]):
        rss = self.get_rss_scraper()
        for source in sources:
            base_url = source.get("base_url") or ""
            source_name = source.get("source_name") or "RSS Institutions"
            country = self.get_or_create_country(
                source.get("country_name") or "International",
                (source.get("country_code") or "XX")[:2].upper(),
            )
            semantic_type = source.get("semantic_type") or "research_centre"

            for feed_url in rss.auto_discover_feeds(base_url):
                items = rss.parse_feed_items(feed_url, max_items=30)
                for item in items:
                    title = self.clean_text(item.get("title") or "")
                    description = self.clean_text(item.get("description") or "")
                    url = (item.get("url") or "").strip()
                    if not title:
                        continue

                    text_blob = f"{title} {description}".lower()
                    if not any(
                        token in text_blob
                        for token in (
                            "lab",
                            "laboratory",
                            "research",
                            "institute",
                            "center",
                            "centre",
                            "university",
                            "ai",
                            "nlp",
                            "machine learning",
                        )
                    ):
                        continue

                    self._create_institution_item(
                        name_en=title,
                        name_ar=title,
                        acronym="",
                        ror_id="",
                        semantic_type=semantic_type,
                        country=country,
                        city_en="",
                        city_ar="",
                        description_en=description
                        or f"Institution update from {source_name}.",
                        description_ar=description
                        or f"Institution update from {source_name}.",
                        website=url or base_url,
                        source_url=feed_url,
                        source_name=f"RSS {source_name}",
                        research_specialties=self._extract_research_areas(description),
                        founding_year=self._extract_founding_year(description),
                        director=self._extract_director(description),
                        affiliated_researchers_count=None,
                        notable_publications=None,
                        social_links=None,
                        logo_url=item.get("image_url") or "",
                    )

    def _scrape_top_lab(self, lab_meta: dict):
        website = lab_meta.get("website", "")
        domain = urlparse(website).netloc or "global-lab"
        country = self.get_or_create_country(
            lab_meta.get("country_name", "International"),
            lab_meta.get("country_code", "XX"),
        )

        bundle = self._fetch_website_bundle(
            [
                website,
                urljoin(website.rstrip("/") + "/", "about"),
                urljoin(website.rstrip("/") + "/", "people"),
                urljoin(website.rstrip("/") + "/", "team"),
                urljoin(website.rstrip("/") + "/", "publications"),
            ],
            source_name=f"Global {domain}",
        )
        merged_text = " ".join(item["text"] for item in bundle)

        director = self._extract_director(merged_text)
        founding_year = self._extract_founding_year(merged_text)
        social_links = self._extract_social_links(bundle)
        logo_url = self._extract_logo_url(bundle, website)
        research_areas = self._extract_research_areas(merged_text)

        self._create_institution_item(
            name_en=lab_meta.get("name", "Global NLP Lab"),
            name_ar=lab_meta.get("name", "Global NLP Lab"),
            acronym="",
            ror_id="",
            semantic_type="lab",
            country=country,
            city_en=lab_meta.get("city", ""),
            city_ar=lab_meta.get("city", ""),
            description_en=self.truncate(merged_text, 1800)
            if merged_text
            else f"{lab_meta.get('name', 'NLP lab')} research group.",
            description_ar=self.truncate(merged_text, 1800)
            if merged_text
            else f"{lab_meta.get('name', 'NLP lab')} research group.",
            website=website,
            source_url=website,
            source_name="Tier4 Global Labs",
            research_specialties=research_areas,
            founding_year=founding_year,
            director=director,
            affiliated_researchers_count=None,
            notable_publications=None,
            social_links=social_links,
            logo_url=logo_url,
        )

    # ------------------------------------------------------------------
    # ROR sync logic (full pagination)
    # ------------------------------------------------------------------

    def _sync_ror_country(self, country_code: str, source_name: str):
        items = self._fetch_ror_country_items(country_code)
        for item in items:
            self._process_ror_item(item, source_name=source_name)

    def _fetch_ror_country_items(self, country_code: str):
        all_items = []
        page = 1
        per_page = 100

        while True:
            resp = self.safe_request(
                self.ROR_BASE,
                params={
                    "filter": f"country.country_code:{country_code}",
                    "page": page,
                    "per_page": per_page,
                },
                timeout=20,
                source_name=f"ROR {country_code}",
            )
            if resp is None:
                break

            try:
                payload = resp.json()
            except Exception:
                break

            items = payload.get("items", [])
            if not items:
                break

            all_items.extend(items)

            if len(items) < per_page:
                break

            page += 1
            if page > 80:
                break

        return all_items

    def _process_ror_item(self, item: dict, source_name: str):
        name = self._extract_ror_name(item)
        if not name:
            return

        aliases = self._extract_ror_aliases(item)
        acronym = self._extract_ror_acronym(item)
        ror_code = self._extract_ror_code(item.get("id") or "")

        locations = item.get("locations") or []
        geonames = (locations[0] or {}).get("geonames_details", {}) if locations else {}
        city = geonames.get("name") or ""
        country_code = geonames.get("country_code") or "XX"
        country_name = geonames.get("country_name") or country_code
        country = self.get_or_create_country(country_name, country_code)

        links = item.get("links") or []
        website_url = self._extract_primary_website_from_ror_links(links)
        semantic_type = self._map_ror_type_to_semantic(item.get("types") or [])

        founding_year = self._extract_founding_year(item.get("established"))

        social_links = {}
        wikipedia_url = ""
        for link in links:
            link_type = str(link.get("type") or "").lower()
            value = str(link.get("value") or "").strip()
            if not value:
                continue
            if link_type == "wikipedia":
                wikipedia_url = value
            if link_type in {"twitter", "linkedin", "github", "facebook", "youtube"}:
                social_links[link_type] = value

        # Enrich with website pages.
        bundle = self._fetch_website_bundle(
            [
                website_url,
                urljoin(website_url.rstrip("/") + "/", "about") if website_url else "",
                urljoin(website_url.rstrip("/") + "/", "contact")
                if website_url
                else "",
                wikipedia_url,
            ],
            source_name=source_name,
        )
        text_blob = " ".join(item_page["text"] for item_page in bundle)

        if not founding_year:
            founding_year = self._extract_founding_year(text_blob)

        director = self._extract_director(text_blob)
        social_links.update(self._extract_social_links(bundle))
        logo_url = self._extract_logo_url(bundle, website_url)

        affiliated_researchers_count = self._extract_affiliated_count_from_openalex(
            item, ror_code
        )
        notable_publications = self._fetch_notable_publications(ror_code)
        research_areas = self._extract_research_areas(text_blob)

        alias_text = f" Aliases: {', '.join(aliases)}." if aliases else ""
        description = f"{name} is a {semantic_type.replace('_', ' ')} institution in {city}, {country_name}.{alias_text}"
        if text_blob:
            description = self.truncate(self.clean_text(text_blob), 1800)

        self._create_institution_item(
            name_en=name,
            name_ar=name,
            acronym=acronym,
            ror_id=ror_code,
            semantic_type=semantic_type,
            country=country,
            city_en=city,
            city_ar=city,
            description_en=description,
            description_ar=description,
            website=website_url,
            source_url=item.get("id") or website_url,
            source_name=source_name,
            research_specialties=research_areas,
            founding_year=founding_year,
            director=director,
            affiliated_researchers_count=affiliated_researchers_count,
            notable_publications=notable_publications,
            social_links=social_links or None,
            logo_url=logo_url,
        )

    @staticmethod
    def _extract_ror_name(item: dict) -> str:
        # v2: names array with typed values.
        names = item.get("names") or []
        for candidate in names:
            types = [str(x).lower() for x in candidate.get("types") or []]
            if "ror_display" in types or "label" in types:
                return str(candidate.get("value") or "").strip()
        if names:
            return str(names[0].get("value") or "").strip()
        # legacy fallback
        return str(item.get("name") or "").strip()

    @staticmethod
    def _extract_ror_aliases(item: dict):
        aliases = []
        for alias in item.get("aliases") or []:
            text = str(alias).strip()
            if text:
                aliases.append(text)
        # v2 fallback from names typed as alias
        for candidate in item.get("names") or []:
            types = [str(x).lower() for x in candidate.get("types") or []]
            if "alias" in types:
                value = str(candidate.get("value") or "").strip()
                if value:
                    aliases.append(value)
        return list(dict.fromkeys(aliases))

    @staticmethod
    def _extract_ror_acronym(item: dict) -> str:
        acronyms = item.get("acronyms") or []
        if acronyms:
            return str(acronyms[0]).strip()[:20]

        for candidate in item.get("names") or []:
            types = [str(x).lower() for x in candidate.get("types") or []]
            if "acronym" in types:
                value = str(candidate.get("value") or "").strip()
                if value:
                    return value[:20]
        return ""

    @staticmethod
    def _extract_ror_code(ror_id: str) -> str:
        text = (ror_id or "").strip()
        if not text:
            return ""
        text = text.rstrip("/")
        if "ror.org/" in text:
            return text.split("ror.org/")[-1]
        return text

    def _map_ror_type_to_semantic(self, types):
        for ror_type in types:
            key = str(ror_type or "").lower()
            if key in TYPE_MAP:
                return TYPE_MAP[key]
        return "university"

    @staticmethod
    def _extract_primary_website_from_ror_links(links) -> str:
        website_url = ""
        for link in links:
            if str(link.get("type") or "").lower() == "website":
                website_url = str(link.get("value") or "").strip()
                if website_url:
                    return website_url
        for link in links:
            value = str(link.get("value") or "").strip()
            if value.startswith("http"):
                return value
        return website_url

    # ------------------------------------------------------------------
    # OpenAlex item / publications enrichment
    # ------------------------------------------------------------------

    def _process_openalex_item(self, item: dict, source_name: str):
        name = str(item.get("display_name") or "").strip()
        if not name:
            return

        ids = item.get("ids") or {}
        openalex_ror = str(ids.get("ror") or "")
        ror_code = self._extract_ror_code(openalex_ror)

        geo = item.get("geo") or {}
        country_code = str(geo.get("country_code") or "XX")
        country_name = str(geo.get("country") or country_code)
        country = self.get_or_create_country(country_name, country_code)
        city = str(geo.get("city") or "")

        website = str(item.get("homepage_url") or "")
        works_count = int(item.get("works_count") or 0)

        semantic_type = self._map_ror_type_to_semantic(
            [str(item.get("type") or "Education")]
        )
        bundle = self._fetch_website_bundle(
            [website, urljoin(website.rstrip("/") + "/", "about") if website else ""],
            source_name="OpenAlex enrichment",
        )
        text_blob = " ".join(part["text"] for part in bundle)

        founding_year = self._extract_founding_year(text_blob)
        director = self._extract_director(text_blob)
        social_links = self._extract_social_links(bundle)
        logo_url = self._extract_logo_url(bundle, website)
        research_areas = self._extract_research_areas(text_blob)

        notable_publications = self._fetch_notable_publications(ror_code)

        self._create_institution_item(
            name_en=name,
            name_ar=name,
            acronym=(item.get("display_name_acronyms") or [""])[0][:20],
            ror_id=ror_code,
            semantic_type=semantic_type,
            country=country,
            city_en=city,
            city_ar=city,
            description_en=self.truncate(self.clean_text(text_blob), 1800)
            if text_blob
            else f"{name} institution profile.",
            description_ar=self.truncate(self.clean_text(text_blob), 1800)
            if text_blob
            else f"{name} institution profile.",
            website=website,
            source_url=item.get("id") or website,
            source_name=source_name,
            research_specialties=research_areas,
            founding_year=founding_year,
            director=director,
            affiliated_researchers_count=works_count if works_count else None,
            notable_publications=notable_publications,
            social_links=social_links,
            logo_url=logo_url,
        )

    def _extract_affiliated_count_from_openalex(self, ror_item: dict, ror_code: str):
        # Prefer direct OpenAlex summary if available in external identifiers.
        ext = ror_item.get("external_ids") or {}
        openalex = ext.get("OpenAlex") or {}
        preferred = openalex.get("preferred") if isinstance(openalex, dict) else None
        if preferred:
            resp = self.safe_request(
                preferred,
                timeout=15,
                source_name="OpenAlex by external_id",
                params={"mailto": "platform@nlp-research.org"},
            )
            if resp is not None:
                try:
                    data = resp.json()
                    works_count = int(data.get("works_count") or 0)
                    if works_count:
                        return works_count
                except (ValueError, TypeError, AttributeError, KeyError) as exc:
                    logger.warning(
                        "openalex_works_count_parse_failed",
                        extra={"error": str(exc), "context": preferred},
                        exc_info=False,
                    )

        if not ror_code:
            return None

        resp = self.safe_request(
            self.OPENALEX_INSTITUTIONS,
            params={
                "filter": f"ror:https://ror.org/{ror_code}",
                "per_page": 1,
                "mailto": "platform@nlp-research.org",
            },
            timeout=15,
            source_name="OpenAlex by ROR",
        )
        if resp is None:
            return None

        try:
            results = resp.json().get("results", [])
            if not results:
                return None
            return int(results[0].get("works_count") or 0) or None
        except Exception:
            return None

    def _fetch_notable_publications(self, ror_code: str):
        if not ror_code:
            return None

        full_ror = f"https://ror.org/{ror_code}"
        resp = self.safe_request(
            self.OPENALEX_WORKS,
            params={
                "filter": f"institutions.ror:{full_ror}",
                "sort": "cited_by_count:desc",
                "per_page": 3,
                "mailto": "platform@nlp-research.org",
            },
            timeout=15,
            source_name="OpenAlex top works",
        )
        if resp is None:
            return None

        try:
            works = resp.json().get("results", [])
        except Exception:
            return None

        entries = []
        for work in works:
            title = str(work.get("display_name") or "").strip()
            if not title:
                continue
            entries.append(
                {
                    "title": title,
                    "cited_by_count": int(work.get("cited_by_count") or 0),
                    "year": work.get("publication_year"),
                    "id": work.get("id"),
                }
            )

        return entries or None

    # ------------------------------------------------------------------
    # Shared extraction / website intelligence
    # ------------------------------------------------------------------

    def _fetch_website_bundle(self, urls, source_name: str):
        pages = []
        seen = set()

        for url in urls:
            normalized = (url or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            if not normalized.startswith("http"):
                continue

            resp = self.safe_request(normalized, timeout=10, source_name=source_name)
            if resp is None:
                continue

            html = resp.text or ""
            text = self._extract_readable_text(html)
            pages.append({"url": normalized, "html": html, "text": text})

        return pages

    def _extract_readable_text(self, html: str):
        soup = BeautifulSoup(html or "", "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        container = (
            soup.find("main")
            or soup.find("article")
            or soup.find(class_=re.compile(r"content|about|team|research", re.I))
            or soup
        )
        text = container.get_text(" ", strip=True)
        return self.clean_text(text)[:7000]

    def _extract_director(self, text: str):
        blob = text or ""
        for pattern in DIRECTOR_PATTERNS:
            match = re.search(pattern, blob, re.I)
            if match:
                return self.clean_text(match.group(1))[:255]
        return None

    def _extract_founding_year(self, value):
        if value is None:
            return None

        if isinstance(value, int):
            if 1800 <= value <= 2100:
                return value
            return None

        text = str(value)
        plain_match = re.search(r"(19\d{2}|20\d{2})", text)
        if plain_match:
            return int(plain_match.group(1))

        for pattern in YEAR_PATTERNS:
            match = re.search(pattern, text, re.I)
            if match:
                return int(match.group(1))

        return None

    def _extract_social_links(self, page_bundles):
        social = {}
        for page in page_bundles:
            soup = BeautifulSoup(page.get("html", ""), "html.parser")
            for anchor in soup.select("a[href]"):
                href = (anchor.get("href") or "").strip()
                if not href.startswith("http"):
                    continue
                lower = href.lower()
                for domain, key in SOCIAL_DOMAINS.items():
                    if domain in lower:
                        social[key] = href

        return social

    def _extract_logo_url(self, page_bundles, base_url: str):
        for page in page_bundles:
            soup = BeautifulSoup(page.get("html", ""), "html.parser")
            og = soup.select_one("meta[property='og:image']")
            if og and og.get("content"):
                return urljoin(page.get("url", base_url), og.get("content"))

            for rel in ["icon", "shortcut icon", "apple-touch-icon"]:
                icon = soup.select_one(f"link[rel='{rel}']")
                if icon and icon.get("href"):
                    return urljoin(page.get("url", base_url), icon.get("href"))

        if base_url:
            return urljoin(base_url.rstrip("/") + "/", "favicon.ico")
        return ""

    def _extract_research_areas(self, text: str):
        blob = (text or "").lower()
        areas = []
        candidates = [
            "natural language processing",
            "nlp",
            "computational linguistics",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "information retrieval",
            "digital libraries",
            "speech processing",
            "text mining",
            "arabic nlp",
        ]
        for item in candidates:
            if item in blob:
                areas.append(item)
        return list(dict.fromkeys(areas))

    def _looks_like_ai_lab(self, text: str):
        blob = (text or "").lower()
        return any(
            token in blob
            for token in [
                "lab",
                "laboratoire",
                "labo",
                "research group",
                "artificial intelligence",
                "machine learning",
                "nlp",
                "lingu",
                "معالجة اللغة",
                "ذكاء اصطناعي",
            ]
        )

    def _extract_lab_cards(self, html: str, page_url: str):
        soup = BeautifulSoup(html or "", "html.parser")
        cards = []
        seen = set()

        for node in soup.select("article, .lab, .laboratoire, .card, li, a"):
            anchor = node if node.name == "a" else node.find("a", href=True)
            if not anchor:
                continue

            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            url = urljoin(page_url, href)
            key = url.rstrip("/")
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

            description = self.clean_text(node.get_text(" ", strip=True))[:1500]
            acronym_match = re.search(r"\(([A-Z0-9\-]{2,12})\)", title)
            cards.append(
                {
                    "name": title[:300],
                    "acronym": acronym_match.group(1) if acronym_match else "",
                    "description": description,
                    "url": url,
                }
            )

        return cards[:80]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _create_institution_item(
        self,
        *,
        name_en,
        name_ar,
        acronym,
        ror_id,
        semantic_type,
        country,
        city_en,
        city_ar,
        description_en,
        description_ar,
        website,
        source_url,
        source_name,
        research_specialties,
        founding_year,
        director,
        affiliated_researchers_count,
        notable_publications,
        social_links,
        logo_url="",
    ):
        from institutions.models import Institution

        if not name_en:
            return None

        media_seed = {
            "name_en": name_en,
            "source_url": source_url,
            "website": website,
            "logo_url": logo_url or "",
        }
        media_seed = self._download_media(media_seed, "institutions")

        is_duplicate, _ = self._check_duplicate_policy(
            "institutions",
            {
                "name_en": name_en,
                "ror_id": (ror_id or "").strip(),
                "website_url": website,
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return None

        model_type = MODEL_TYPE_MAP.get(semantic_type, "University")

        item_dict = {
            "name_en": name_en,
            "name_ar": name_ar or name_en,
            "acronym": acronym or "",
            "ror_id": ror_id or "",
            "institution_type": model_type,
            "country": country,
            "city_en": city_en or "",
            "city_ar": city_ar or city_en or "",
            "description_en": description_en or "",
            "description_ar": description_ar or description_en or "",
            "website": website or "",
            "address_en": f"{city_en}, {getattr(country, 'name_en', '')}".strip(", "),
            "address_ar": f"{city_ar}, {getattr(country, 'name_ar', getattr(country, 'name_en', ''))}".strip(
                ", "
            ),
            "logo_url": logo_url or "",
            "research_specialties": research_specialties or [],
            "founding_year": founding_year,
            "director": director,
            "affiliated_researchers_count": affiliated_researchers_count,
            "notable_publications": notable_publications,
            "social_links": social_links,
            "source_url": source_url,
            "source_name": source_name,
            "image_local_path": media_seed.get("image_local_path") or "",
            "image_content_file": media_seed.get("image_content_file"),
        }

        item_dict = enrich_scraped_item(item_dict, "institutions")
        completeness = calculate_completeness_score(item_dict, "institutions")
        if completeness < 35:
            self.items_skipped += 1
            return None

        is_valid, item_dict, _ = self.validate_and_prepare(item_dict, "institutions")
        if not is_valid:
            self.items_skipped += 1
            return None

        try:
            institution = Institution.objects.create(
                name=item_dict.get("name_en", "")[:255],
                name_en=item_dict.get("name_en", "")[:255],
                name_ar=item_dict.get("name_ar", "")[:255],
                acronym=item_dict.get("acronym", "")[:20],
                ror_id=item_dict.get("ror_id", ""),
                type=model_type,
                country=country,
                city=item_dict.get("city_en", "")[:100],
                city_en=item_dict.get("city_en", "")[:100],
                city_ar=item_dict.get("city_ar", "")[:100],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                website=item_dict.get("website", ""),
                email="",
                phone="",
                address=item_dict.get("address_en", ""),
                address_en=item_dict.get("address_en", ""),
                address_ar=item_dict.get("address_ar", ""),
                research_specialties=", ".join(
                    item_dict.get("research_specialties", [])
                ),
                founding_year=item_dict.get("founding_year"),
                director=item_dict.get("director"),
                affiliated_researchers_count=item_dict.get(
                    "affiliated_researchers_count"
                ),
                notable_publications=item_dict.get("notable_publications"),
                social_links=item_dict.get("social_links"),
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
                approval_status="pending",
                created_by=self.get_system_user(),
            )

            image_local_path = item_dict.get("image_local_path") or ""
            if image_local_path:
                try:
                    attach_file_to_model(
                        institution,
                        "logo",
                        item_dict.get("image_content_file"),
                        image_local_path,
                    )
                except (AttributeError, KeyError, ValueError, OSError) as exc:
                    logger.warning(
                        "institution_logo_attach_failed",
                        extra={
                            "error": str(exc),
                            "context": item_dict.get("name_en") or name_en,
                        },
                        exc_info=False,
                    )
                    try:
                        attach_file_to_model(
                            institution,
                            "image",
                            item_dict.get("image_content_file"),
                            image_local_path,
                        )
                    except (
                        AttributeError,
                        KeyError,
                        ValueError,
                        OSError,
                    ) as fallback_exc:
                        logger.warning(
                            "institution_image_attach_failed",
                            extra={
                                "error": str(fallback_exc),
                                "context": item_dict.get("website") or name_en,
                            },
                            exc_info=False,
                        )

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("name_en", name_en), 90),
                    "type": model_type,
                    "country": getattr(country, "name_en", ""),
                    "city": item_dict.get("city_en", ""),
                    "url": item_dict.get("website", ""),
                    "ror_id": item_dict.get("ror_id", ""),
                }
            )
            return institution
        except Exception as exc:
            self.errors.append(
                f"Failed to create institution '{self.truncate(name_en, 80)}': {exc}"
            )
            logger.error("Institution creation failed for %s: %s", name_en, exc)
            return None
