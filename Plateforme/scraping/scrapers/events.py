"""
NLP Events scraper — sources: WikiCFP + curated fallback list of major
NLP / CL conferences.
"""

import re
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

# ── Well-known NLP conference organising bodies ──────────────────────
CONFERENCE_ORGS = {
    "ACL": {"name": "Association for Computational Linguistics", "code": "US"},
    "EMNLP": {"name": "Association for Computational Linguistics", "code": "US"},
    "NAACL": {"name": "Association for Computational Linguistics", "code": "US"},
    "EACL": {"name": "European Chapter of ACL", "code": "DE"},
    "COLING": {
        "name": "International Committee on Computational Linguistics",
        "code": "US",
    },
    "LREC": {"name": "European Language Resources Association", "code": "FR"},
    "AAAI": {"name": "Association for the Advancement of AI", "code": "US"},
    "IJCAI": {"name": "International Joint Conferences on AI", "code": "US"},
    "AACL": {"name": "Asia-Pacific Chapter of ACL", "code": "JP"},
    "SIGIR": {"name": "ACM Special Interest Group on IR", "code": "US"},
    "WSDM": {"name": "ACM WSDM", "code": "US"},
    "ANLP": {"name": "Arabic NLP Community", "code": "SA"},
    "IEEE": {"name": "IEEE Computer Society", "code": "US"},
}

# ── Curated future NLP events (used when live scraping yields nothing) ──
CURATED_EVENTS = [
    {
        "title": "ACL 2025 — 63rd Annual Meeting of the Association for Computational Linguistics",
        "description": "The premier international conference on computational linguistics and NLP, featuring research papers, tutorials, workshops, and demos on all aspects of language technology.",
        "event_type": "conference",
        "domains": "nlp,computational_linguistics,ai",
        "location": "Vienna, Austria",
        "start_date": "2025-07-27",
        "end_date": "2025-08-01",
        "submission_deadline": "2025-02-15",
        "website": "https://2025.aclweb.org/",
        "contact_email": "acl2025@aclweb.org",
        "org_key": "ACL",
    },
    {
        "title": "EMNLP 2025 — Conference on Empirical Methods in Natural Language Processing",
        "description": "A major NLP conference focused on empirical methods and their application to language processing tasks including text classification, machine translation, and information extraction.",
        "event_type": "conference",
        "domains": "nlp,machine_learning,ai",
        "location": "Suzhou, China",
        "start_date": "2025-11-05",
        "end_date": "2025-11-09",
        "submission_deadline": "2025-06-01",
        "website": "https://2025.emnlp.org/",
        "contact_email": "emnlp2025@emnlp.org",
        "org_key": "EMNLP",
    },
    {
        "title": "NAACL 2025 — North American Chapter of the ACL",
        "description": "Annual conference of the North American Chapter of the Association for Computational Linguistics bringing together researchers in NLP, speech, and information retrieval.",
        "event_type": "conference",
        "domains": "nlp,speech,ai",
        "location": "Albuquerque, New Mexico, USA",
        "start_date": "2025-04-29",
        "end_date": "2025-05-04",
        "submission_deadline": "2024-10-15",
        "website": "https://2025.naacl.org/",
        "contact_email": "naacl2025@naacl.org",
        "org_key": "NAACL",
    },
    {
        "title": "COLING 2025 — 31st International Conference on Computational Linguistics",
        "description": "One of the oldest international conferences on computational linguistics, covering theoretical and applied aspects of NLP including Arabic NLP.",
        "event_type": "conference",
        "domains": "nlp,linguistics,arabic_lang",
        "location": "Abu Dhabi, UAE",
        "start_date": "2025-01-19",
        "end_date": "2025-01-24",
        "submission_deadline": "2024-09-16",
        "website": "https://coling2025.org/",
        "contact_email": "info@coling2025.org",
        "org_key": "COLING",
    },
    {
        "title": "EACL 2025 — European Chapter of the ACL",
        "description": "The European chapter gathering for the ACL community. Covers research on European and under-resourced languages, including Arabic dialect processing.",
        "event_type": "conference",
        "domains": "nlp,linguistics,ai",
        "location": "Dubrovnik, Croatia",
        "start_date": "2025-03-31",
        "end_date": "2025-04-04",
        "submission_deadline": "2024-10-15",
        "website": "https://2025.eacl.org/",
        "contact_email": "eacl2025@eacl.org",
        "org_key": "EACL",
    },
    {
        "title": "AAAI 2025 — AAAI Conference on Artificial Intelligence",
        "description": "Premier AI conference covering all areas of artificial intelligence including NLP, knowledge representation, planning, and machine learning.",
        "event_type": "conference",
        "domains": "ai,nlp,machine_learning",
        "location": "Philadelphia, Pennsylvania, USA",
        "start_date": "2025-02-25",
        "end_date": "2025-03-04",
        "submission_deadline": "2024-08-15",
        "website": "https://aaai.org/conference/aaai/aaai-25/",
        "contact_email": "aaai25@aaai.org",
        "org_key": "AAAI",
    },
    {
        "title": "IJCNLP-AACL 2025 — International Joint Conference on NLP",
        "description": "Joint conference of the International Joint Conference on NLP and Asia-Pacific ACL chapter, highlighting NLP research from Asia-Pacific including Arabic NLP.",
        "event_type": "conference",
        "domains": "nlp,arabic_lang,ai",
        "location": "Bali, Indonesia",
        "start_date": "2025-10-01",
        "end_date": "2025-10-04",
        "submission_deadline": "2025-05-15",
        "website": "https://www.ijcnlp-aacl2025.org/",
        "contact_email": "info@ijcnlp-aacl2025.org",
        "org_key": "AACL",
    },
    {
        "title": "ArabicNLP 2025 — Workshop on Arabic Natural Language Processing",
        "description": "Dedicated workshop for Arabic NLP research including morphological analysis, dialectal Arabic processing, sentiment analysis, and machine translation for Arabic.",
        "event_type": "workshop",
        "domains": "nlp,arabic_lang,linguistics,sentiment_analysis",
        "location": "Vienna, Austria",
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "submission_deadline": "2025-05-15",
        "website": "https://arabicnlp2025.sigarab.org/",
        "contact_email": "arabicnlp2025@sigarab.org",
        "org_key": "ANLP",
    },
    {
        "title": "LREC-COLING 2025 — Language Resources and Evaluation Conference",
        "description": "Conference on language resources, evaluation methods, and tools. Special focus on low-resource languages and corpus creation for Arabic dialects.",
        "event_type": "conference",
        "domains": "nlp,linguistics,arabic_lang",
        "location": "Torino, Italy",
        "start_date": "2025-05-20",
        "end_date": "2025-05-25",
        "submission_deadline": "2024-12-01",
        "website": "https://lrec-coling-2025.org/",
        "contact_email": "info@lrec-coling-2025.org",
        "org_key": "LREC",
    },
    {
        "title": "SIGIR 2025 — 48th International ACM SIGIR Conference",
        "description": "The premier research conference in information retrieval, featuring work on search, recommendation, and NLP for information access.",
        "event_type": "conference",
        "domains": "nlp,ai,information_retrieval",
        "location": "Padua, Italy",
        "start_date": "2025-07-13",
        "end_date": "2025-07-18",
        "submission_deadline": "2025-01-22",
        "website": "https://sigir2025.org/",
        "contact_email": "sigir2025@acm.org",
        "org_key": "SIGIR",
    },
    {
        "title": "NeurIPS 2025 — Conference on Neural Information Processing Systems",
        "description": "Top machine learning conference featuring cutting-edge research on deep learning for NLP, transformers, large language models, and multimodal AI.",
        "event_type": "conference",
        "domains": "ai,nlp,machine_learning",
        "location": "San Diego, California, USA",
        "start_date": "2025-12-09",
        "end_date": "2025-12-15",
        "submission_deadline": "2025-05-22",
        "website": "https://neurips.cc/",
        "contact_email": "info@neurips.cc",
        "org_key": "ACL",
    },
    {
        "title": "WANLP 2025 — Workshop on Arabic NLP (co-located with EMNLP)",
        "description": "WANLP brings together researchers working on Arabic Natural Language Processing including MSA and dialectal Arabic, covering tasks such as POS tagging, NER, and text generation.",
        "event_type": "workshop",
        "domains": "nlp,arabic_lang,sentiment_analysis,machine_translation",
        "location": "Suzhou, China",
        "start_date": "2025-11-09",
        "end_date": "2025-11-09",
        "submission_deadline": "2025-08-15",
        "website": "https://wanlp2025.github.io/",
        "contact_email": "wanlp2025@googlegroups.com",
        "org_key": "ANLP",
    },
]


class EventScraper(BaseScraper):
    """Scrape NLP events from WikiCFP and a curated conference list."""

    name = "NLP Events Scraper"
    category = "events"

    def scrape(self):
        """Run all event-scraping strategies in order."""
        self._scrape_wikicfp()
        self._import_curated_events()

    # ── WikiCFP ──────────────────────────────────────────────────────
    def _scrape_wikicfp(self):
        """Attempt to scrape upcoming NLP events from WikiCFP search."""
        url = "http://www.wikicfp.com/cfp/servlet/tool.search"
        for query in (
            "natural language processing",
            "NLP",
            "computational linguistics",
        ):
            resp = self.safe_request(url, params={"q": query, "year": "f"})
            if resp is None:
                continue

            try:
                from bs4 import BeautifulSoup  # type: ignore[import-unresolved]

                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.select("table.imark tr")
                if not rows:
                    rows = soup.find_all("tr", class_="imark")

                i = 0
                while i < len(rows):
                    try:
                        cells = rows[i].find_all("td")
                        if len(cells) < 2:
                            i += 1
                            continue

                        # Row 1: abbreviation (link) + full title
                        link_tag = cells[0].find("a")
                        abbr = cells[0].get_text(strip=True)
                        full_title = (
                            cells[1].get_text(strip=True) if len(cells) > 1 else abbr
                        )
                        event_url = ""
                        if link_tag and link_tag.get("href"):
                            href = link_tag["href"]
                            event_url = (
                                href
                                if href.startswith("http")
                                else f"http://www.wikicfp.com{href}"
                            )

                        # Row 2: dates + location
                        i += 1
                        if i < len(rows):
                            cells2 = rows[i].find_all("td")
                            dates_str = (
                                cells2[0].get_text(strip=True)
                                if len(cells2) > 0
                                else ""
                            )
                            location = (
                                cells2[1].get_text(strip=True)
                                if len(cells2) > 1
                                else ""
                            )
                        else:
                            dates_str, location = "", ""

                        title = (
                            f"{abbr} — {full_title}"
                            if full_title and full_title != abbr
                            else abbr
                        )
                        start, end = self._parse_date_range(dates_str)

                        if start:
                            self._create_event(
                                title=title,
                                description=f"NLP conference/workshop: {full_title}",
                                location=location,
                                start_date=start,
                                end_date=end or start,
                                website=event_url,
                                org_key=abbr.split()[0].upper(),
                            )
                    except Exception as exc:
                        logger.debug("WikiCFP row parse error: %s", exc)
                    i += 1

            except ImportError:
                self.errors.append(
                    "beautifulsoup4 is not installed — WikiCFP scraping skipped"
                )
            except Exception as exc:
                self.errors.append(f"WikiCFP parse error for '{query}': {exc}")

    # ── Curated fallback ─────────────────────────────────────────────
    def _import_curated_events(self):
        """Import well-known NLP conferences from the curated list."""
        for item in CURATED_EVENTS:
            self._create_event(
                title=item["title"],
                description=item["description"],
                event_type=item.get("event_type", "conference"),
                domains=item.get("domains", "nlp"),
                location=item.get("location", ""),
                start_date=self.parse_date(item["start_date"]),
                end_date=self.parse_date(item["end_date"]),
                submission_deadline=self.parse_date(
                    item.get("submission_deadline", "")
                ),
                website=item.get("website", ""),
                contact_email=item.get("contact_email", ""),
                org_key=item.get("org_key", ""),
            )

    # ── Helpers ──────────────────────────────────────────────────────
    def _create_event(
        self,
        *,
        title,
        description="",
        event_type="conference",
        domains="nlp",
        location="",
        start_date=None,
        end_date=None,
        submission_deadline=None,
        website="",
        contact_email="",
        org_key="",
    ):
        from events.models import Event

        if not start_date:
            self.items_skipped += 1
            return

        # Duplicate check
        if Event.objects.filter(title_en__iexact=title).exists():
            self.items_skipped += 1
            return
        if website and Event.objects.filter(website=website).exists():
            self.items_skipped += 1
            return

        organizer = self._resolve_organizer(org_key)
        if organizer is None:
            self.items_skipped += 1
            self.errors.append(f"Could not resolve organizer for: {title}")
            return

        try:
            Event.objects.create(
                title=title,
                title_en=title,
                title_ar=title,
                description=description,
                description_en=description,
                description_ar=description,
                event_type=event_type,
                domains=domains,
                location=location,
                location_en=location,
                location_ar=location,
                start_date=start_date,
                end_date=end_date or start_date,
                submission_deadline=submission_deadline,
                website=website or "",
                contact_email=contact_email or "info@conference.org",
                organizer=organizer,
                created_by=self.get_system_user(),
                approval_status="pending",
                is_approved=False,
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(title, 100),
                    "location": location,
                    "dates": f"{start_date} → {end_date}",
                    "url": website,
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create event '{title}': {exc}")
            logger.error("Failed to create event %s: %s", title, exc)

    def _resolve_organizer(self, org_key):
        """Get or create an Institution that acts as the event organiser."""
        info = CONFERENCE_ORGS.get(org_key)
        if info:
            country = self.get_or_create_country(info["name"][:30], info["code"])
            return self.get_or_create_institution(
                info["name"],
                inst_type="Other",
                country=country,
                acronym=org_key,
            )
        # Generic fallback
        country = self.get_or_create_country("International", "XX")
        return self.get_or_create_institution(
            "NLP Research Community",
            inst_type="Other",
            country=country,
            acronym="NLP",
        )

    def _parse_date_range(self, text):
        """Parse a date-range string like 'Aug 11, 2025 - Aug 16, 2025'."""
        if not text:
            return None, None
        parts = re.split(r"\s*[-–—]\s*", text, maxsplit=1)
        start = self.parse_date(parts[0])
        end = self.parse_date(parts[1]) if len(parts) > 1 else start
        return start, end
