import logging
import re
from urllib.parse import urljoin, urlparse

from django.utils import timezone

from scraping.constants import (
    EVENT_DEFAULT_DISCOVERY_PATHS,
    EVENT_PRIORITY_SCORES,
    SCRAPER_BOT_EMAIL,
)
from scraping.enrichment_engine import enrich_scraped_item
from scraping.field_mapping import calculate_completeness_score
from scraping.file_downloader import attach_file_to_model
from scraping.fixture_loader import load_event_type_keywords
from scraping.models import ScrapedItemMeta
from scraping.scrapers.playwright_scraper import PlaywrightFallbackScraper
from scraping.scraping_settings import scraping_settings as SS  # noqa: N812

logger = logging.getLogger(__name__)


class EventScraper(PlaywrightFallbackScraper):
    name = "NLP Events Scraper"
    category = "events"
    SECTION = "events"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_type_keywords = load_event_type_keywords()

    @classmethod
    def get_default_sources(cls):
        from scraping.models import ScrapingSource

        return ScrapingSource.objects.filter(
            category=cls.SECTION,
            is_default=True,
        ).order_by("name")

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
        sources = list(self.get_active_sources())
        if not sources:
            sources = list(self.get_default_sources())

        if not sources:
            logger.warning("No active/default event sources configured.")
            return

        def _has_source_url(source):
            return (getattr(source, "url", "") or source.base_url or "").strip()

        sources = [source for source in sources if _has_source_url(source)]
        if not sources:
            sources = [
                source
                for source in self.get_default_sources()
                if _has_source_url(source)
            ]
            if sources:
                logger.info(
                    "Falling back to default event sources after filtering empty active URLs."
                )

        if not sources:
            logger.warning("No configured/default event sources had a valid URL.")
            return

        combined = []
        for source in sources:
            source_url = (getattr(source, "url", "") or source.base_url or "").strip()

            scrape_config = dict(getattr(source, "scrape_config", {}) or {})
            source_name = (
                getattr(source, "name", "Configured Source") or "Configured Source"
            )

            combined.extend(
                self._collect_from_source(
                    source=source,
                    base_url=source_url,
                    source_name=source_name,
                    priority=self._to_int(
                        scrape_config.get("priority_score"),
                        EVENT_PRIORITY_SCORES["global"],
                    ),
                    tier=self._to_int(scrape_config.get("tier"), 1),
                    default_location=scrape_config.get("default_location") or "Unknown",
                    timeout=self._to_int(
                        scrape_config.get("timeout"), SS.TOTAL_TIMEOUT
                    ),
                    paths=self._extract_paths_from_scrape_config(scrape_config),
                    scrape_config=scrape_config,
                )
            )

        if not combined:
            logger.warning(
                "No event candidates extracted from configured active sources."
            )
            return

        deduped_candidates = self._deduplicate_combined_candidates(combined)
        created_before = self.items_created

        for candidate in deduped_candidates:
            self._save_event_candidate(candidate)

        if self.items_created == created_before:
            logger.info(
                "Candidates were extracted from configured sources but none passed validation or duplicate checks."
            )

    def _extract_paths_from_scrape_config(self, scrape_config):
        raw_paths = scrape_config.get("paths") or scrape_config.get("discovery_paths")
        if isinstance(raw_paths, str):
            parsed = [
                segment.strip() for segment in raw_paths.split(",") if segment.strip()
            ]
            return parsed or None
        if isinstance(raw_paths, list):
            parsed = [str(path).strip() for path in raw_paths if str(path).strip()]
            return parsed or None
        return None

    def _to_int(self, value, default_value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default_value)

    def _collect_from_source(
        self,
        *,
        source,
        base_url,
        source_name,
        priority,
        tier,
        default_location,
        timeout=SS.TOTAL_TIMEOUT,
        paths=None,
        scrape_config=None,
    ):
        collected = []

        rss_scraper = self.get_rss_scraper()
        feed_url_list = rss_scraper.auto_discover_feeds(base_url)
        items = self.scrape_rss_sources(feed_url_list)
        collected.extend(
            self._convert_rss_to_candidates(
                rss_items=items,
                source_name=source_name,
                source_url=base_url,
                priority=priority,
                tier=tier,
                default_location=default_location,
            )
        )

        html_paths = paths or EVENT_DEFAULT_DISCOVERY_PATHS
        collected.extend(
            self._collect_html_paths(
                base_url=base_url,
                paths=html_paths,
                source_name=source_name,
                source=source,
                priority=priority,
                tier=tier,
                default_location=default_location,
                timeout=timeout,
                scrape_config=scrape_config,
            )
        )
        return collected

    def _collect_html_paths(
        self,
        *,
        base_url,
        paths,
        source_name,
        source=None,
        priority,
        tier,
        default_location,
        timeout,
        scrape_config=None,
    ):
        collected = []
        for path in paths:
            page_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            try:
                collected.extend(
                    self.paginate_listing(
                        listing_url=page_url,
                        extract_fn=self._extract_event_candidates,
                        extract_kwargs={
                            "source_name": source_name,
                            "source": source,
                            "default_location": default_location,
                            "priority": priority,
                            "tier": tier,
                        },
                        timeout=timeout,
                        scrape_config=scrape_config,
                        source_name=source_name,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed parsing source=%s url=%s err=%s", source_name, page_url, exc
                )
        return collected

    def _extract_event_candidates(
        self,
        *,
        soup,
        page_url,
        source_name,
        source,
        default_location,
        priority,
        tier,
    ):
        return self._extract_event_candidates_from_html(
            soup=soup,
            page_url=page_url,
            source_name=source_name,
            source=source,
            default_location=default_location,
            priority=priority,
            tier=tier,
        )

    def _extract_event_candidates_from_html(
        self,
        *,
        soup,
        page_url,
        source_name,
        source,
        default_location,
        priority,
        tier,
    ):
        candidates = []
        selectors = dict(getattr(source, "css_selectors", {}) or {}) if source else {}
        warned_selector_fallback = False

        containers = soup.select(
            "article, .post, .news-item, .event-item, .card, li, tr"
        )
        if not containers:
            containers = [soup]

        for node in containers[: SS.LISTING_MAX_CONTAINERS]:
            event_url = page_url
            try:
                admin_result = (
                    self._extract_with_admin_selectors(
                        soup,
                        source,
                        container=node,
                    )
                    if source is not None
                    else None
                )

                if admin_result:
                    title = self.clean_text(admin_result.get("title") or "")
                    raw_text = self.clean_text(
                        " ".join(
                            part
                            for part in (
                                admin_result.get("body") or "",
                                admin_result.get("date_raw") or "",
                                admin_result.get("author") or "",
                            )
                            if part
                        )
                    )
                    if not raw_text:
                        raw_text = self.clean_text(node.get_text(" ", strip=True))

                    selected_url = (admin_result.get("url") or "").strip()
                    if selected_url:
                        event_url = urljoin(page_url, selected_url)

                    registration_link = self._extract_registration_link(node, page_url)
                    extracted_date = self.parse_date(admin_result.get("date_raw") or "")
                    if not extracted_date:
                        extracted_date = self._extract_date(raw_text)
                    location = self._extract_location(raw_text) or default_location
                    description = self.clean_text(admin_result.get("body") or "")
                    if not description:
                        description = self._build_description(node, raw_text)
                    event_type = self._extract_event_type(title, raw_text)
                else:
                    if selectors.get("title_selector") and not warned_selector_fallback:
                        logger.warning(
                            "Admin selectors configured for %s but extraction returned nothing — check selectors in admin panel.",
                            getattr(source, "url", "") or page_url,
                        )
                        warned_selector_fallback = True

                    title_tag = node.find(["h1", "h2", "h3", "h4", "a"])
                    if not title_tag:
                        continue
                    title = self.clean_text(title_tag.get_text(" ", strip=True))

                    raw_text = self.clean_text(node.get_text(" ", strip=True))

                    link_tag = node.find("a", href=True)
                    if link_tag:
                        event_url = urljoin(page_url, link_tag.get("href", ""))

                    registration_link = self._extract_registration_link(node, page_url)
                    extracted_date = self._extract_date(raw_text)
                    location = self._extract_location(raw_text) or default_location
                    description = self._build_description(node, raw_text)
                    event_type = self._extract_event_type(title, raw_text)

                if not title or len(title) < 8:
                    continue
                if not self._is_event_like_text(f"{title} {raw_text}"):
                    continue

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
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "event_candidate_skipped_due_to_error",
                    extra={
                        "error": str(exc),
                        "item": event_url or page_url,
                    },
                    exc_info=False,
                )
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
        date_is_inferred = False
        if not start_date:
            inferred = self._extract_date(
                " ".join(
                    [
                        candidate.get("title", "") or "",
                        candidate.get("description", "") or "",
                        candidate.get("source_url", "") or "",
                    ]
                )
            )
            if inferred:
                start_date = inferred
                date_is_inferred = True
            else:
                # Keep pipeline resilient when sources omit explicit dates.
                start_date = timezone.now().date()
                date_is_inferred = True

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
        if date_is_inferred and "date_unverified" not in tags:
            tags = list(tags) + ["date_unverified"]

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
            "contact_email": SCRAPER_BOT_EMAIL,
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
        if completeness < SS.EVENTS_COMPLETENESS_MIN:
            self.items_skipped += 1
            return

        valid, item_dict, _ = self.validate_and_prepare(item_dict, "events")
        if not valid:
            self.items_skipped += 1
            return

        if not self.passes_llm_confidence_gate(item_dict, "events"):
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
                entities=item_dict.get("entities", {}),
                organizer=organizer,
                contact_email=item_dict.get("contact_email") or SCRAPER_BOT_EMAIL,
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
                except (AttributeError, KeyError, ValueError, OSError) as exc:
                    logger.warning(
                        "event_media_attach_failed",
                        extra={
                            "error": str(exc),
                            "context": item_dict.get("title_en") or title,
                            "field": "banner_image",
                        },
                        exc_info=False,
                    )

            attachment_path = item_dict.get("pdf_local_path") or ""
            if attachment_path:
                try:
                    attach_file_to_model(
                        event,
                        "attachment",
                        item_dict.get("pdf_content_file"),
                        attachment_path,
                    )
                except (AttributeError, KeyError, ValueError, OSError) as exc:
                    logger.warning(
                        "event_media_attach_failed",
                        extra={
                            "error": str(exc),
                            "context": item_dict.get("title_en") or title,
                            "field": "attachment",
                        },
                        exc_info=False,
                    )
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
                    candidate.get("priority_score") or EVENT_PRIORITY_SCORES["global"]
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
                        int(
                            candidate.get("priority_score")
                            or EVENT_PRIORITY_SCORES["global"]
                        )
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
        keyword_map = getattr(self, "_event_type_keywords", None)
        if keyword_map is None:
            keyword_map = load_event_type_keywords()
            self._event_type_keywords = keyword_map

        for event_type, keywords in (keyword_map or {}).items():
            if any(keyword and keyword in blob for keyword in keywords):
                return event_type

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
