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
    "SIGARAB": {"name": "ACL Special Interest Group on Arabic NLP", "code": "SA"},
    "AICS": {"name": "AI Conference Series — MENA", "code": "AE"},
    "ICNLSP": {"name": "ICNLSP Organising Committee", "code": "DZ"},
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
    # ── Arabic / North African / MENA Events ──
    {
        "title": "ICNLSP 2025 — 8th International Conference on Natural Language and Speech Processing",
        "description": "ICNLSP focuses on NLP and speech processing for Arabic and under-resourced languages. Covers morphological analysis, dialect identification, ASR, and TTS for Arabic variants.",
        "event_type": "conference",
        "domains": "nlp,arabic_lang,speech_processing",
        "location": "Algiers, Algeria",
        "start_date": "2025-12-13",
        "end_date": "2025-12-14",
        "submission_deadline": "2025-09-15",
        "website": "https://www.icnlsp.org/",
        "contact_email": "contact@icnlsp.org",
        "org_key": "ICNLSP",
    },
    {
        "title": "ArabicNLP 2025 — 6th Workshop on Arabic NLP (co-located with ACL)",
        "description": "The flagship Arabic NLP workshop co-located with ACL. Covers Arabic morphological analysis, dialectal Arabic, machine translation, sentiment analysis, and Arabic LLMs.",
        "event_type": "workshop",
        "domains": "nlp,arabic_lang,machine_translation,sentiment_analysis",
        "location": "Vienna, Austria",
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "submission_deadline": "2025-05-20",
        "website": "https://arabicnlp2025.sigarab.org/",
        "contact_email": "arabicnlp@sigarab.org",
        "org_key": "SIGARAB",
    },
    {
        "title": "ICALP 2025 — International Conference on Arabic Language Processing",
        "description": "Conference dedicated to Arabic language processing including NLP, text mining, information retrieval, and speech technology for Arabic and its dialects.",
        "event_type": "conference",
        "domains": "nlp,arabic_lang,speech_processing",
        "location": "Rabat, Morocco",
        "start_date": "2025-10-15",
        "end_date": "2025-10-17",
        "submission_deadline": "2025-07-01",
        "website": "https://icalp.org/",
        "contact_email": "info@icalp.org",
        "org_key": "SIGARAB",
    },
    {
        "title": "AI & NLP Summit MENA 2025",
        "description": "Industry and academic summit focused on AI and NLP applications in the MENA region, including Arabic chatbots, Arabic LLMs, and Arabic speech technology.",
        "event_type": "conference",
        "domains": "nlp,arabic_lang,llm_research,ai",
        "location": "Dubai, UAE",
        "start_date": "2025-09-22",
        "end_date": "2025-09-24",
        "submission_deadline": "2025-06-15",
        "website": "https://ainlpsummit.com/",
        "contact_email": "info@ainlpsummit.com",
        "org_key": "AICS",
    },
    {
        "title": "North Africa AI Summit 2025",
        "description": "Regional summit bringing together AI researchers and practitioners from Algeria, Morocco, Tunisia, Libya, and Egypt. Covers NLP, computer vision, and AI for development.",
        "event_type": "conference",
        "domains": "ai,nlp,arabic_lang",
        "location": "Tunis, Tunisia",
        "start_date": "2025-11-18",
        "end_date": "2025-11-20",
        "submission_deadline": "2025-08-01",
        "website": "https://northafricaaisummit.org/",
        "contact_email": "contact@northafricaaisummit.org",
        "org_key": "AICS",
    },
    {
        "title": "NADI 2025 — Nuanced Arabic Dialect Identification Shared Task",
        "description": "Annual shared task on Arabic dialect identification covering 21 Arab countries. Includes subtasks on dialect-to-MSA translation and country-level dialect detection.",
        "event_type": "workshop",
        "domains": "nlp,arabic_lang,machine_translation",
        "location": "Vienna, Austria",
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "submission_deadline": "2025-05-15",
        "website": "https://nadi.dlnlp.ai/",
        "contact_email": "nadi@dlnlp.ai",
        "org_key": "ANLP",
    },
    {
        "title": "Deep Learning Indaba 2025",
        "description": "Africa's premier machine learning conference. Features research on African and Arabic NLP, low-resource language processing, and AI for African development.",
        "event_type": "conference",
        "domains": "ai,nlp,machine_learning",
        "location": "Dakar, Senegal",
        "start_date": "2025-09-07",
        "end_date": "2025-09-12",
        "submission_deadline": "2025-04-30",
        "website": "https://deeplearningindaba.com/",
        "contact_email": "info@deeplearningindaba.com",
        "org_key": "ACL",
    },
    {
        "title": "IEEE AICCSA 2025 — ACS/IEEE International Conference on Computer Systems and Applications",
        "description": "Long-running conference covering computer systems and applications in the Arab world, with dedicated tracks on Arabic NLP, text mining, and machine learning.",
        "event_type": "conference",
        "domains": "nlp,ai,arabic_lang",
        "location": "Cairo, Egypt",
        "start_date": "2025-12-01",
        "end_date": "2025-12-04",
        "submission_deadline": "2025-08-15",
        "website": "https://www.aiccsa.net/",
        "contact_email": "aiccsa@ieee.org",
        "org_key": "IEEE",
    },
    {
        "title": "SIGARAB Workshop on Computational Approaches to Arabic Script Languages",
        "description": "Workshop on computational approaches to Arabic-script languages including Arabic, Farsi, Urdu, and Amazigh. Covers OCR, text normalization, and script-specific NLP.",
        "event_type": "workshop",
        "domains": "nlp,arabic_lang,linguistics",
        "location": "Suzhou, China",
        "start_date": "2025-11-09",
        "end_date": "2025-11-09",
        "submission_deadline": "2025-08-01",
        "website": "https://sigarab.org/",
        "contact_email": "sigarab@googlegroups.com",
        "org_key": "SIGARAB",
    },
]


class EventScraper(BaseScraper):
    """Scrape NLP events from WikiCFP and a curated conference list."""

    name = "NLP Events Scraper"
    category = "events"

    def scrape(self):
        """Run all event-scraping strategies in order."""
        self._scrape_wikicfp()
        self._scrape_conferencealerts_algeria()
        self._scrape_allconferencealert_algeria()
        self._scrape_conferencealerts_country("morocco")
        self._scrape_conferencealerts_country("tunisia")
        self._scrape_conferencealerts_country("egypt")
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

    # ── ConferenceAlerts.co.in — generic country scraper ────────────
    def _scrape_conferencealerts_country(self, country: str):
        """Scrape conferences for a given country from conferencealerts.co.in."""
        url = f"https://conferencealerts.co.in/{country}"
        resp = self.safe_request(url)
        if resp is None:
            return

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".conf-list .conf-item, .event-list li, table tr") or soup.find_all("div", class_=re.compile(r"conf|event"))

            for card in cards:
                try:
                    link_tag = card.find("a")
                    if not link_tag:
                        continue
                    title = link_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    href = link_tag.get("href", "")
                    event_url = href if href.startswith("http") else f"https://conferencealerts.co.in{href}"

                    text = card.get_text(" ", strip=True)
                    date_match = re.search(
                        r"(\d{1,2}\s+\w+\s+\d{4})"
                        r"|(\w+\s+\d{1,2}[-–]\d{1,2},?\s+\d{4})"
                        r"|(\d{4}-\d{2}-\d{2})",
                        text,
                    )
                    start = self.parse_date(date_match.group(0)) if date_match else None

                    city = ""
                    city_match = re.search(r"(?:City|Location|Venue)[:\s]+([^,\n]+)", text, re.I)
                    if city_match:
                        city = city_match.group(1).strip()
                    country_name = country.title()
                    location = f"{city}, {country_name}" if city else country_name

                    self._create_event(
                        title=title,
                        description=f"Conference in {country_name}: {title}",
                        event_type="conference",
                        domains="nlp,ai",
                        location=location,
                        start_date=start,
                        end_date=start,
                        website=event_url,
                        org_key="",
                    )
                except Exception as exc:
                    logger.debug("conferencealerts.co.in %s parse error: %s", country, exc)

        except ImportError:
            self.errors.append("beautifulsoup4 not installed — country scraping skipped")
        except Exception as exc:
            self.errors.append(f"conferencealerts.co.in/{country} error: {exc}")

    # ── ConferenceAlerts.co.in — Algeria ──────────────────────────────
    def _scrape_conferencealerts_algeria(self):
        """Scrape conferences in Algeria from conferencealerts.co.in."""
        url = "https://conferencealerts.co.in/algeria"
        resp = self.safe_request(url)
        if resp is None:
            return

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            # Each conference is typically in a card / list-item block
            cards = soup.select(".conf-list .conf-item, .event-list li, table tr") or soup.find_all("div", class_=re.compile(r"conf|event"))

            for card in cards:
                try:
                    # Title + link
                    link_tag = card.find("a")
                    if not link_tag:
                        continue
                    title = link_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    href = link_tag.get("href", "")
                    event_url = href if href.startswith("http") else f"https://conferencealerts.co.in{href}"

                    # Extract text for date / city parsing
                    text = card.get_text(" ", strip=True)

                    # Try to find date (common patterns: "12 Mar 2026", "March 12-14, 2026")
                    date_match = re.search(
                        r"(\d{1,2}\s+\w+\s+\d{4})"
                        r"|(\w+\s+\d{1,2}[-–]\d{1,2},?\s+\d{4})"
                        r"|(\d{4}-\d{2}-\d{2})",
                        text,
                    )
                    start = self.parse_date(date_match.group(0)) if date_match else None

                    # City — often after the date or labelled "City:"
                    city = ""
                    city_match = re.search(r"(?:City|Location|Venue)[:\s]+([^,\n]+)", text, re.I)
                    if city_match:
                        city = city_match.group(1).strip()
                    location = f"{city}, Algeria" if city else "Algeria"

                    self._create_event(
                        title=title,
                        description=f"Conference in Algeria: {title}",
                        event_type="conference",
                        domains="nlp,ai",
                        location=location,
                        start_date=start,
                        end_date=start,
                        website=event_url,
                        org_key="",
                    )
                except Exception as exc:
                    logger.debug("conferencealerts.co.in parse error: %s", exc)

        except ImportError:
            self.errors.append("beautifulsoup4 not installed — Algeria scraping skipped")
        except Exception as exc:
            self.errors.append(f"conferencealerts.co.in error: {exc}")

    # ── AllConferenceAlert — Algeria ─────────────────────────────────
    def _scrape_allconferencealert_algeria(self):
        """Scrape conferences in Algeria from allconferencealert.com."""
        url = "https://www.allconferencealert.com/algeria.html"
        resp = self.safe_request(url)
        if resp is None:
            return

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            # Events are in table rows or card blocks
            rows = soup.select("table.searchResult tr, .conf-box, .event-item") or soup.find_all("tr")

            for row in rows:
                try:
                    link_tag = row.find("a")
                    if not link_tag:
                        continue
                    title = link_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    href = link_tag.get("href", "")
                    event_url = href if href.startswith("http") else f"https://www.allconferencealert.com/{href}"

                    cells = row.find_all("td")
                    date_str = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    city = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    category = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                    start = self.parse_date(date_str) if date_str else None
                    location = f"{city}, Algeria" if city else "Algeria"

                    self._create_event(
                        title=title,
                        description=f"Conference in Algeria ({category}): {title}",
                        event_type="conference",
                        domains="nlp,ai",
                        location=location,
                        start_date=start,
                        end_date=start,
                        website=event_url,
                        org_key="",
                    )
                except Exception as exc:
                    logger.debug("allconferencealert.com parse error: %s", exc)

        except ImportError:
            self.errors.append("beautifulsoup4 not installed — Algeria scraping skipped")
        except Exception as exc:
            self.errors.append(f"allconferencealert.com error: {exc}")

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

        # ── LLM validation & enrichment (non-blocking) ──────────────
        try:
            from scraping.llm_validation import validate_item, apply_llm_enrichment

            raw_item = {
                "title": title,
                "description": description,
                "event_type": event_type,
                "domains": domains,
                "location": location,
                "start_date": str(start_date) if start_date else "",
                "end_date": str(end_date) if end_date else "",
                "submission_deadline": str(submission_deadline) if submission_deadline else "",
                "website": website,
                "contact_email": contact_email,
            }
            enriched = validate_item(raw_item, category="events")

            if enriched is not None:
                # Skip items the LLM flags as spam or irrelevant
                if enriched.get("is_spam"):
                    self.items_skipped += 1
                    self.errors.append(
                        f"LLM flagged as spam: '{title}' — {enriched.get('spam_reason', '')}"
                    )
                    return
                if not enriched.get("is_relevant", True):
                    self.items_skipped += 1
                    self.errors.append(
                        f"LLM flagged as irrelevant: '{title}' — {enriched.get('relevance_reason', '')}"
                    )
                    return

                # Apply enriched translations & filled fields
                merged = apply_llm_enrichment(raw_item, enriched)
                title = merged.get("title_en") or title
                title_ar = merged.get("title_ar") or title
                description = merged.get("description_en") or description
                description_ar = merged.get("description_ar") or description
                contact_email = merged.get("contact_email") or contact_email
                location = merged.get("location") or location
                logger.info(
                    "LLM enriched event '%s' (score=%s)",
                    title, enriched.get("quality_score"),
                )
            else:
                title_ar = title
                description_ar = description
        except Exception as llm_exc:
            # LLM failure must never prevent saving
            logger.debug("LLM validation failed for '%s': %s", title, llm_exc)
            title_ar = title
            description_ar = description

        try:
            Event.objects.create(
                title=title,
                title_en=title,
                title_ar=title_ar,
                description=description,
                description_en=description,
                description_ar=description_ar,
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
