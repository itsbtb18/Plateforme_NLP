"""
Tiered NLP events scraper with Algerian-first source priority.

Execution order:
  Tier 1: Algerian sources (always first)
  Tier 2: Arabic/MENA sources
  Tier 3: African sources
  Tier 4: Global sources
"""

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import attach_file_to_model
from scraping.field_mapping import calculate_completeness_score
from scraping.models import ScrapedItemMeta
from scraping.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


PRIORITY_SCORE = {
    "algerian": 100,
    "mena": 75,
    "african": 50,
    "global": 25,
}


ALGERIAN_UNIVERSITIES = [
    "https://www.univ-alger.dz",
    "https://www.univ-oran.dz",
    "https://www.umc.edu.dz",
    "https://www.univ-constantine.dz",
    "https://www.univ-annaba.dz",
    "https://www.univ-bejaia.dz",
    "https://www.univ-tizi-ouzou.dz",
]


ALGERIAN_DISCOVERY_PATHS = ["/actualites", "/events", "/agenda", "/news"]


MENA_DISCOVERY_SOURCES = [
    ("https://sigarab.github.io", "SIGARAB"),
    ("https://arabicnlp.org", "ArabicNLP"),
    ("https://aclanthology.org/venues/wanlp/", "ArabicNLP ACL Anthology"),
    ("https://www.kfupm.edu.sa", "KFUPM"),
    ("https://www.aub.edu.lb", "AUB"),
    ("https://www.kaust.edu.sa", "KAUST"),
]


AFRICAN_DISCOVERY_SOURCES = [
    ("https://deeplearningindaba.com", "Deep Learning Indaba"),
    ("https://aclanthology.org/venues/africanlp/", "AfricaNLP ACL Anthology"),
    ("https://www.masakhane.io", "Masakhane"),
]


GLOBAL_WIKICFP_TOPICS = ["cs.AI", "cs.LG", "cs.CL"]


class EventScraper(BaseScraper):
    name = "NLP Events Scraper"
    category = "events"

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

    def scrape(self):
        tier_1 = self._scrape_tier_1_events()
        tier_2 = self._scrape_tier_2_events()
        tier_3 = self._scrape_tier_3_events()
        tier_4 = self._scrape_tier_4_events()

        combined = tier_1 + tier_2 + tier_3 + tier_4
        deduped_candidates = self._deduplicate_combined_candidates(combined)

        for candidate in deduped_candidates:
            self._save_event_candidate(candidate)

    def _scrape_tier_1_events(self):
        results = []
        results.extend(self._scrape_esi_events())
        results.extend(self._scrape_usthb_events())
        results.extend(self._scrape_ummto_events())
        results.extend(self._scrape_dgrsdt_events())
        results.extend(self._scrape_mesrs_events())
        results.extend(self._scrape_algerian_university_network())
        return results

    def _scrape_tier_2_events(self):
        results = []
        for base_url, source_name in MENA_DISCOVERY_SOURCES:
            results.extend(
                self._collect_from_source(
                    base_url=base_url,
                    source_name=source_name,
                    priority=PRIORITY_SCORE["mena"],
                    tier=2,
                    default_location="MENA",
                    timeout=20,
                )
            )
        return results

    def _scrape_tier_3_events(self):
        results = []
        for base_url, source_name in AFRICAN_DISCOVERY_SOURCES:
            results.extend(
                self._collect_from_source(
                    base_url=base_url,
                    source_name=source_name,
                    priority=PRIORITY_SCORE["african"],
                    tier=3,
                    default_location="Africa",
                    timeout=20,
                )
            )
        return results

    def _scrape_tier_4_events(self):
        results = []
        results.extend(self._scrape_wikicfp_enhanced())
        results.extend(self._scrape_acl_anthology_calendar())
        results.extend(self._scrape_semantic_scholar_venues())
        return results

    def _scrape_esi_events(self):
        base = "https://www.esi.dz"
        paths = ["/category/events/", "/events/", "/actualites/"]
        return self._collect_html_paths(
            base_url=base,
            paths=paths,
            source_name="ESI",
            priority=PRIORITY_SCORE["algerian"],
            tier=1,
            default_location="Algiers, Algeria",
            timeout=10,
        )

    def _scrape_usthb_events(self):
        return self._collect_from_source(
            base_url="https://www.usthb.dz",
            source_name="USTHB",
            priority=PRIORITY_SCORE["algerian"],
            tier=1,
            default_location="Algiers, Algeria",
            timeout=10,
            paths=["/actualites", "/events", "/agenda", "/news"],
        )

    def _scrape_ummto_events(self):
        return self._collect_from_source(
            base_url="https://www.ummto.dz",
            source_name="UMMTO",
            priority=PRIORITY_SCORE["algerian"],
            tier=1,
            default_location="Tizi Ouzou, Algeria",
            timeout=10,
            paths=["/actualites", "/events", "/agenda", "/news"],
        )

    def _scrape_dgrsdt_events(self):
        return self._collect_from_source(
            base_url="https://www.dgrsdt.dz",
            source_name="DGRSDT",
            priority=PRIORITY_SCORE["algerian"],
            tier=1,
            default_location="Algeria",
            timeout=10,
            paths=["/actualites", "/appels-a-projets", "/events", "/agenda"],
        )

    def _scrape_mesrs_events(self):
        return self._collect_from_source(
            base_url="https://www.mesrs.dz",
            source_name="MESRS",
            priority=PRIORITY_SCORE["algerian"],
            tier=1,
            default_location="Algeria",
            timeout=10,
            paths=["/actualites", "/communiques", "/agenda", "/events"],
        )

    def _scrape_algerian_university_network(self):
        candidates = []
        for university_url in ALGERIAN_UNIVERSITIES:
            source_name = self._source_name_from_url(university_url)
            try:
                candidates.extend(
                    self._collect_from_source(
                        base_url=university_url,
                        source_name=source_name,
                        priority=PRIORITY_SCORE["algerian"],
                        tier=1,
                        default_location="Algeria",
                        timeout=10,
                        paths=ALGERIAN_DISCOVERY_PATHS,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Skipping Algerian university source=%s error=%s",
                    university_url,
                    exc,
                )
                continue
        return candidates

    def _collect_from_source(
        self,
        *,
        base_url,
        source_name,
        priority,
        tier,
        default_location,
        timeout=20,
        paths=None,
    ):
        collected = []

        rss_scraper = self.get_rss_scraper()
        for feed_url in rss_scraper.auto_discover_feeds(base_url):
            rss_items = rss_scraper.parse_feed_items(feed_url, max_items=50)
            collected.extend(
                self._convert_rss_to_candidates(
                    rss_items=rss_items,
                    source_name=source_name,
                    source_url=feed_url,
                    priority=priority,
                    tier=tier,
                    default_location=default_location,
                )
            )

        html_paths = paths or ALGERIAN_DISCOVERY_PATHS
        collected.extend(
            self._collect_html_paths(
                base_url=base_url,
                paths=html_paths,
                source_name=source_name,
                priority=priority,
                tier=tier,
                default_location=default_location,
                timeout=timeout,
            )
        )
        return collected

    def _collect_html_paths(
        self,
        *,
        base_url,
        paths,
        source_name,
        priority,
        tier,
        default_location,
        timeout,
    ):
        collected = []
        for path in paths:
            page_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            response = self.safe_request(
                page_url, timeout=timeout, source_name=source_name
            )
            if not response:
                logger.info(
                    "source_page_skipped",
                    extra={
                        "category": self.category,
                        "source_name": source_name,
                        "source_url": page_url,
                        "skip_reason": "no_response",
                    },
                )
                continue
            if response.status_code >= 400:
                logger.info(
                    "source_page_skipped",
                    extra={
                        "category": self.category,
                        "source_name": source_name,
                        "source_url": page_url,
                        "skip_reason": "http_error",
                        "status_code": response.status_code,
                    },
                )
                continue
            try:
                collected.extend(
                    self._extract_event_candidates_from_html(
                        html=response.text,
                        page_url=page_url,
                        source_name=source_name,
                        default_location=default_location,
                        priority=priority,
                        tier=tier,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed parsing source=%s url=%s err=%s", source_name, page_url, exc
                )
        return collected

    def _extract_event_candidates_from_html(
        self,
        *,
        html,
        page_url,
        source_name,
        default_location,
        priority,
        tier,
    ):
        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        containers = soup.select(
            "article, .post, .news-item, .event-item, .card, li, tr"
        )
        if not containers:
            containers = [soup]

        for node in containers[:180]:
            try:
                title_tag = node.find(["h1", "h2", "h3", "h4", "a"])
                if not title_tag:
                    continue
                title = self.clean_text(title_tag.get_text(" ", strip=True))
                if not title or len(title) < 8:
                    continue

                raw_text = self.clean_text(node.get_text(" ", strip=True))
                if not self._is_event_like_text(f"{title} {raw_text}"):
                    continue

                link_tag = node.find("a", href=True)
                event_url = page_url
                if link_tag:
                    event_url = urljoin(page_url, link_tag.get("href", ""))

                registration_link = self._extract_registration_link(node, page_url)
                extracted_date = self._extract_date(raw_text)
                location = self._extract_location(raw_text) or default_location
                description = self._build_description(node, raw_text)
                event_type = self._extract_event_type(title, raw_text)

                candidates.append(
                    {
                        "title": title,
                        "description": description,
                        "event_type": event_type,
                        "location": location,
                        "start_date": extracted_date,
                        "end_date": extracted_date,
                        "submission_deadline": None,
                        "notification_date": None,
                        "website": event_url,
                        "registration_link": registration_link,
                        "source_url": page_url,
                        "source_name": source_name,
                        "priority_score": priority,
                        "tier": tier,
                        "domains": "nlp,ai",
                        "tags": self._build_tags(
                            title, description, event_type, source_name
                        ),
                        "language": self._infer_language(f"{title} {description}"),
                    }
                )
            except Exception:
                continue

        return candidates

    def _convert_rss_to_candidates(
        self,
        *,
        rss_items,
        source_name,
        source_url,
        priority,
        tier,
        default_location,
    ):
        candidates = []
        for item in rss_items:
            title = self.clean_text(item.get("title") or item.get("title_en", ""))
            if not title:
                continue

            description = self.clean_text(
                item.get("description") or item.get("description_en", "")
            )
            text_blob = f"{title} {description}"
            if not self._is_event_like_text(text_blob):
                continue

            event_type = self._extract_event_type(title, text_blob)
            date_value = item.get("published_date")
            start_date = (
                date_value.date() if hasattr(date_value, "date") else date_value
            )

            candidates.append(
                {
                    "title": title,
                    "description": description,
                    "event_type": event_type,
                    "location": default_location,
                    "start_date": start_date,
                    "end_date": start_date,
                    "submission_deadline": None,
                    "notification_date": None,
                    "website": item.get("url", ""),
                    "registration_link": "",
                    "source_url": source_url,
                    "source_name": source_name,
                    "priority_score": priority,
                    "tier": tier,
                    "domains": "nlp,ai",
                    "tags": self._build_tags(
                        title, description, event_type, source_name
                    ),
                    "language": self._infer_language(text_blob),
                }
            )
        return candidates

    def _scrape_wikicfp_enhanced(self):
        url = "http://www.wikicfp.com/cfp/servlet/tool.search"
        search_terms = [
            "natural language processing",
            "arabic nlp",
            "african nlp",
            "computational linguistics",
        ]
        candidates = []

        for query in search_terms:
            for topic in GLOBAL_WIKICFP_TOPICS:
                response = self.safe_request(
                    url,
                    params={"q": f"{query} {topic}", "year": "f"},
                    source_name="WikiCFP",
                )
                if not response:
                    continue
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                    rows = soup.select("table.imark tr")
                    i = 0
                    while i < len(rows):
                        row = rows[i]
                        cells = row.find_all("td")
                        if len(cells) < 2:
                            i += 1
                            continue

                        link_tag = cells[0].find("a", href=True)
                        title_head = self.clean_text(cells[1].get_text(" ", strip=True))
                        if not title_head:
                            i += 1
                            continue

                        event_url = url
                        if link_tag:
                            event_url = urljoin(
                                "http://www.wikicfp.com", link_tag.get("href", "")
                            )

                        next_text = ""
                        if i + 1 < len(rows):
                            next_text = self.clean_text(
                                rows[i + 1].get_text(" ", strip=True)
                            )

                        merged = f"{title_head} {next_text}"
                        if not self._wikicfp_focus_filter(merged):
                            i += 2
                            continue

                        date_guess = self._extract_date(merged)
                        location = self._extract_location(merged) or "Global"
                        event_type = self._extract_event_type(title_head, merged)

                        candidates.append(
                            {
                                "title": title_head,
                                "description": self.truncate(merged, 1000),
                                "event_type": event_type,
                                "location": location,
                                "start_date": date_guess,
                                "end_date": date_guess,
                                "submission_deadline": None,
                                "notification_date": None,
                                "website": event_url,
                                "registration_link": "",
                                "source_url": url,
                                "source_name": "WikiCFP",
                                "priority_score": PRIORITY_SCORE["global"],
                                "tier": 4,
                                "domains": "nlp,ai",
                                "tags": self._build_tags(
                                    title_head, merged, event_type, "WikiCFP"
                                ),
                                "language": self._infer_language(merged),
                            }
                        )
                        i += 2
                except Exception as exc:
                    logger.warning(
                        "WikiCFP parse failed query=%s topic=%s err=%s",
                        query,
                        topic,
                        exc,
                    )

        return candidates

    def _scrape_acl_anthology_calendar(self):
        candidates = []
        endpoints = [
            "https://aclanthology.org/search/?q=workshop+arabic+nlp",
            "https://aclanthology.org/search/?q=conference+africanlp",
            "https://aclanthology.org/search/?q=sigarab+workshop",
        ]

        for endpoint in endpoints:
            response = self.safe_request(endpoint, source_name="ACL Anthology")
            if not response:
                continue
            try:
                candidates.extend(
                    self._extract_event_candidates_from_html(
                        html=response.text,
                        page_url=endpoint,
                        source_name="ACL Anthology",
                        default_location="Global",
                        priority=PRIORITY_SCORE["global"],
                        tier=4,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "ACL Anthology parse failed url=%s err=%s", endpoint, exc
                )

        return candidates

    def _scrape_semantic_scholar_venues(self):
        candidates = []
        api = "https://api.semanticscholar.org/graph/v1/paper/search"
        queries = [
            "Arabic NLP workshop",
            "conference computational linguistics Africa",
            "SIGARAB workshop",
        ]

        for query in queries:
            response = self.safe_request(
                api,
                params={
                    "query": query,
                    "fields": "title,venue,year,url,publicationDate",
                    "limit": 20,
                },
                source_name="Semantic Scholar",
            )
            if not response:
                continue
            try:
                payload = response.json()
                for paper in payload.get("data", []):
                    title = self.clean_text(paper.get("title", ""))
                    venue = self.clean_text(paper.get("venue", ""))
                    if not title:
                        continue
                    merged = f"{title} {venue}"
                    if not self._is_event_like_text(merged):
                        continue
                    if not self._wikicfp_focus_filter(merged):
                        continue

                    pub_date = self.parse_date(paper.get("publicationDate", ""))
                    event_type = self._extract_event_type(title, merged)
                    candidates.append(
                        {
                            "title": title,
                            "description": self.truncate(merged, 1000),
                            "event_type": event_type,
                            "location": "Global",
                            "start_date": pub_date,
                            "end_date": pub_date,
                            "submission_deadline": None,
                            "notification_date": None,
                            "website": paper.get("url", "") or "",
                            "registration_link": "",
                            "source_url": api,
                            "source_name": "Semantic Scholar",
                            "priority_score": PRIORITY_SCORE["global"],
                            "tier": 4,
                            "domains": "nlp,ai",
                            "tags": self._build_tags(
                                title, merged, event_type, "Semantic Scholar"
                            ),
                            "language": self._infer_language(merged),
                        }
                    )
            except Exception as exc:
                logger.warning(
                    "Semantic Scholar parse failed query=%s err=%s", query, exc
                )

        return candidates

    def _deduplicate_combined_candidates(self, candidates):
        deduped = []
        seen_keys = set()

        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                -(c.get("priority_score") or 0),
                c.get("source_name", ""),
                c.get("title", ""),
            ),
        )

        for item in sorted_candidates:
            title_key = self._normalize_text(item.get("title", ""))
            website_key = self._normalize_url(item.get("website", ""))
            date_key = str(item.get("start_date") or "")
            key = (title_key, website_key, date_key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)

        return deduped

    def _save_event_candidate(self, candidate):
        from events.models import Event

        title = (candidate.get("title") or "").strip()
        if not title:
            self.items_skipped += 1
            return

        start_date = candidate.get("start_date")
        if not start_date:
            self.items_skipped += 1
            return

        start_date = (
            self.parse_date(str(start_date))
            if isinstance(start_date, str)
            else start_date
        )
        if not start_date:
            self.items_skipped += 1
            return

        end_date = candidate.get("end_date")
        end_date = (
            self.parse_date(str(end_date)) if isinstance(end_date, str) else end_date
        )
        if not end_date:
            end_date = start_date

        organizer = self._resolve_organizer(candidate)
        if organizer is None:
            self.items_skipped += 1
            return

        description = candidate.get("description") or title
        event_type = self._normalize_model_event_type(candidate.get("event_type"))
        language = candidate.get("language") or self._infer_language(
            f"{title} {description}"
        )
        tags = candidate.get("tags") or self._build_tags(
            title,
            description,
            candidate.get("event_type") or "conference",
            candidate.get("source_name") or "unknown",
        )

        item_dict = {
            "title_en": title,
            "title_ar": title,
            "description_en": description,
            "description_ar": description,
            "start_date": start_date,
            "end_date": end_date,
            "submission_deadline": candidate.get("submission_deadline"),
            "notification_date": candidate.get("notification_date"),
            "location_en": candidate.get("location", ""),
            "location_ar": candidate.get("location", ""),
            "website": candidate.get("website", ""),
            "registration_link": candidate.get("registration_link") or None,
            "is_online": "online" in (candidate.get("location", "") or "").lower(),
            "is_hybrid": "hybrid" in f"{title} {description}".lower(),
            "source_url": candidate.get("source_url", ""),
            "source_name": candidate.get("source_name", ""),
            "language": language,
            "tags": tags,
            "contact_email": "scraper-bot@nlp-platform.local",
            "event_type": event_type,
            "research_domains": candidate.get("domains", "nlp,ai"),
            "banner_image_url": candidate.get("banner_image_url")
            or candidate.get("image_url")
            or "",
            "pdf_attachments": candidate.get("pdf_attachments") or [],
        }

        item_dict = self._download_media(item_dict, "events")

        policy_duplicate, _ = self._check_duplicate_policy(
            "events",
            {
                "title_en": item_dict.get("title_en", title),
                "website_url": item_dict.get("website", candidate.get("website", "")),
                "organizer": organizer,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        if policy_duplicate:
            self.items_skipped += 1
            return

        item_dict = enrich_scraped_item(item_dict, "events")
        completeness = calculate_completeness_score(item_dict, "events")
        if completeness < 35:
            self.items_skipped += 1
            return

        valid, item_dict, _ = self.validate_and_prepare(item_dict, "events")
        if not valid:
            self.items_skipped += 1
            return

        try:
            event = Event.objects.create(
                title=item_dict.get("title_en", "")[:255],
                title_en=item_dict.get("title_en", "")[:255],
                title_ar=item_dict.get("title_ar", "")[:255],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                event_type=item_dict.get("event_type", "conference"),
                domains=item_dict.get("research_domains", "nlp"),
                location=item_dict.get("location_en", "")[:255],
                location_en=item_dict.get("location_en", "")[:255],
                location_ar=item_dict.get("location_ar", "")[:255],
                start_date=item_dict.get("start_date"),
                end_date=item_dict.get("end_date") or item_dict.get("start_date"),
                submission_deadline=item_dict.get("submission_deadline"),
                notification_date=item_dict.get("notification_date"),
                website=item_dict.get("website", ""),
                registration_link=item_dict.get("registration_link"),
                is_online=bool(item_dict.get("is_online", False)),
                is_hybrid=bool(item_dict.get("is_hybrid", False)),
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
                language=item_dict.get("language") or "en",
                tags=item_dict.get("tags") or None,
                organizer=organizer,
                contact_email=item_dict.get("contact_email")
                or "scraper-bot@nlp-platform.local",
                approval_status="pending",
                created_by=self.get_system_user(),
                source="scrape",
            )

            banner_path = item_dict.get("image_local_path") or ""
            if banner_path:
                try:
                    attach_file_to_model(
                        event,
                        "banner_image",
                        item_dict.get("image_content_file"),
                        banner_path,
                    )
                except Exception:
                    pass

            attachment_path = item_dict.get("pdf_local_path") or ""
            if attachment_path:
                try:
                    attach_file_to_model(
                        event,
                        "attachment",
                        item_dict.get("pdf_content_file"),
                        attachment_path,
                    )
                except Exception:
                    pass
        except Exception as exc:
            self.errors.append(f"Failed to create event '{title}': {exc}")
            return

        self._store_priority_meta(event, item_dict, candidate)

        self.items_created += 1
        self.results.append(
            {
                "title": item_dict.get("title_en", title),
                "description": self.truncate(
                    item_dict.get("description_en", description), 400
                ),
                "type": item_dict.get("event_type", "conference"),
                "url": item_dict.get("website", ""),
                "location": item_dict.get("location_en", ""),
                "priority_score": int(
                    candidate.get("priority_score") or PRIORITY_SCORE["global"]
                ),
            }
        )

    def _store_priority_meta(self, event, item_dict, candidate):
        try:
            ScrapedItemMeta.objects.update_or_create(
                category="events",
                item_title=(item_dict.get("title_en") or "")[:300],
                defaults={
                    "item_id": str(event.id),
                    "primary_domain": "arabic_nlp",
                    "domain_scores": {"arabic_nlp": 1.0},
                    "relevance_score": float(
                        int(candidate.get("priority_score") or PRIORITY_SCORE["global"])
                    ),
                    "completeness_score": float(
                        calculate_completeness_score(item_dict, "events")
                    ),
                },
            )
        except Exception as exc:
            logger.debug("priority meta upsert failed event=%s err=%s", event.id, exc)

    def _resolve_organizer(self, candidate):
        source_name = candidate.get("source_name") or "NLP Research Community"
        location = candidate.get("location", "")

        country_name = "International"
        country_code = "XX"
        if "alger" in location.lower() or "algeria" in location.lower():
            country_name = "Algeria"
            country_code = "DZ"

        country = self.get_or_create_country(country_name, country_code)
        return self.get_or_create_institution(
            source_name,
            inst_type="Other",
            country=country,
            acronym=self._source_acronym(source_name),
            website=self._source_base_url(candidate.get("source_url", "")),
        )

    def _source_acronym(self, source_name):
        tokens = [t for t in re.split(r"\W+", source_name.upper()) if t]
        if not tokens:
            return "NLP"
        if len(tokens) == 1:
            return tokens[0][:10]
        return "".join(token[0] for token in tokens[:6])[:10]

    def _source_name_from_url(self, url):
        hostname = urlparse(url).netloc.lower().replace("www.", "")
        root = hostname.split(".")[0]
        return root.upper() if root else "UNIVERSITY"

    def _source_base_url(self, url):
        parsed = urlparse(url or "")
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_registration_link(self, node, page_url):
        for anchor in node.find_all("a", href=True):
            label = self.clean_text(anchor.get_text(" ", strip=True)).lower()
            if any(
                k in label
                for k in ["register", "registration", "apply", "inscription", "join"]
            ):
                return urljoin(page_url, anchor.get("href", ""))
        return ""

    def _build_description(self, node, fallback_text):
        paragraphs = [
            self.clean_text(p.get_text(" ", strip=True))
            for p in node.find_all("p")
            if self.clean_text(p.get_text(" ", strip=True))
        ]
        if paragraphs:
            return self.truncate(" ".join(paragraphs), 1200)
        return self.truncate(fallback_text, 1200)

    def _extract_date(self, text):
        if not text:
            return None

        patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
            r"\b[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                parsed = self.parse_date(match.group(0))
                if parsed:
                    return parsed
        return None

    def _extract_location(self, text):
        if not text:
            return ""

        patterns = [
            r"(?:location|venue|city|lieu)\s*[:\-]\s*([^\n|]+)",
            r"\b(Algiers|Alger|Oran|Constantine|Annaba|Bejaia|Tizi Ouzou|Algeria)\b",
            r"\b(Dubai|Riyadh|Jeddah|Abu Dhabi|Doha|Kuwait|Cairo|Rabat|Tunis)\b",
            r"\b(Africa|Global|Online|Virtual)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                return self.clean_text(value)[:255]
        return ""

    def _extract_event_type(self, title, description):
        blob = f"{title} {description}".lower()
        if "hackathon" in blob:
            return "hackathon"
        if "call for papers" in blob or " cfp" in blob or "cfp " in blob:
            return "cfp"
        if "workshop" in blob:
            return "workshop"
        if "seminar" in blob or "webinar" in blob:
            return "seminar"
        if "conference" in blob:
            return "conference"
        return "conference"

    def _normalize_model_event_type(self, event_type):
        value = (event_type or "conference").strip().lower()
        if value == "cfp":
            return "call_for_papers"
        if value in {"conference", "workshop", "seminar", "hackathon"}:
            return value
        return "conference"

    def _is_event_like_text(self, text):
        blob = (text or "").lower()
        event_keywords = [
            "conference",
            "workshop",
            "seminar",
            "webinar",
            "event",
            "symposium",
            "colloquium",
            "hackathon",
            "call for papers",
            "cfp",
            "agenda",
            "actualite",
            "actualites",
        ]
        return any(keyword in blob for keyword in event_keywords)

    def _wikicfp_focus_filter(self, text):
        blob = (text or "").lower()
        focus_keywords = [
            "algeria",
            "alger",
            "arabic",
            "mena",
            "africa",
            "north africa",
            "maghreb",
            "darija",
        ]
        return any(keyword in blob for keyword in focus_keywords)

    def _build_tags(self, title, description, event_type, source_name):
        blob = f"{title} {description} {source_name}".lower()
        tags = ["nlp", "events", event_type]
        for token in [
            "arabic",
            "africa",
            "algeria",
            "workshop",
            "conference",
            "cfp",
            "seminar",
        ]:
            if token in blob and token not in tags:
                tags.append(token)
        return tags

    def _infer_language(self, text):
        content = text or ""
        if re.search(r"[\u0600-\u06FF]", content):
            return "ar"
        lowered = content.lower()
        if any(
            token in lowered
            for token in ["francais", "français", "universite", "algérie"]
        ):
            return "fr"
        return "en"
