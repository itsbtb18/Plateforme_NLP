import logging
import re
from datetime import date, timedelta
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.utils import timezone

from scraping.constants import EVENT_PRIORITY_SCORES, SCRAPER_BOT_EMAIL
from scraping.extractors.events.llm_event_extractor import LLMEventExtractor
from scraping.field_mapping import get_auto_translate_fields
from scraping.models import ScrapedItemMeta
from scraping.network.search_client import TavilySearchClient
from scraping.scrapers.base import BaseScraper
from scraping.scraping_settings import scraping_settings as SS  # noqa: N812
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

logger = logging.getLogger(__name__)


class EventScraper(BaseScraper):
    name = "NLP Events Scraper"
    category = "events"

    DEFAULT_EVENT_SEARCH_QUERY_TEMPLATES = (
        "upcoming arabic nlp conferences {year}",
        "upcoming nlp conferences {year}",
        "nlp workshops in mena {year}",
        "search for coming nlp events in algeria {year}",
        "call for papers computational linguistics {year}",
        "speech processing workshops {year}",
        "arabic nlp shared task {year}",
        "ai conference middle east {year}",
        "nlp conference africa {year}",
        "international conference on natural language processing {year}",
    )

    BLOCKED_SOURCE_HOSTS = {
        "wikicfp.com",
        "aclanthology.org",
        "allconferencealert.com",
        "allconferencealert.net",
        "conferencealert.com",
        "conferencealerts.com",
        "conferencealerts.co.in",
        "conferenceindex.org",
        "internationalconferencealerts.com",
        "resurchify.com",
    }

    WEB_DISCOVERY_SOURCE_NAME = "Global Web Discovery"
    WEB_DISCOVERY_QUERY_TEMPLATES = (
        "upcoming arabic nlp conference {year}",
        "arabic nlp workshop {year}",
        "call for papers computational linguistics {year}",
        "ai conference middle east {year}",
        "nlp conference africa {year}",
        "shared task arabic nlp {year}",
    )
    WEB_DISCOVERY_EXCLUDED_HOSTS = {
        "allconferencealert.com",
        "conferencealerts.com",
    }
    WEB_DISCOVERY_EVENT_URL_TOKENS = (
        "conference",
        "workshop",
        "seminar",
        "symposium",
        "summit",
        "hackathon",
        "cfp",
        "call-for-papers",
        "shared-task",
        "challenge",
        "2026",
        "2027",
    )
    WEB_DISCOVERY_FALLBACK_URL_TEMPLATES = (
        "https://{year}.aclweb.org",
        "https://{year}.naacl.org",
        "https://{year}.emnlp.org",
        "https://acm.org/conferences",
        "https://iclr.cc",
        "https://neurips.cc",
    )
    WEB_DISCOVERY_TRUSTED_HOST_TOKENS = (
        "aclweb",
        "acm",
        "ieee",
        "aaai",
        "neurips",
        "iclr",
        "icml",
        "coling",
        "emnlp",
        "naacl",
        "eacl",
        "lrec",
        "interspeech",
    )
    LISTING_TITLE_PATTERNS = (
        "conferences in ",
        "conference in ",
        "upcoming conferences",
        "top conference cities",
        "events in ",
        "conference overview",
        "events list",
        "conferences & calls for papers",
    )
    LISTING_BODY_PATTERNS = (
        "top conference cities",
        "currently, there are",
        "upcoming conferences across all regions",
        "accounting for approximately",
        "premier destination for global knowledge exchange",
    )
    EVENT_SIGNAL_TOKENS = (
        "conference",
        "workshop",
        "seminar",
        "symposium",
        "summit",
        "call for papers",
        "cfp",
        "hackathon",
        "shared task",
        "challenge",
    )
    TOPIC_RELEVANCE_TOKENS = (
        "nlp",
        "natural language",
        "computational linguistics",
        "language model",
        "large language model",
        "speech",
        "asr",
        "ai",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "text mining",
        "information retrieval",
        "arabic",
    )
    TOPIC_RELEVANCE_EVENT_CODES = (
        "acl",
        "emnlp",
        "naacl",
        "eacl",
        "coling",
        "lrec",
        "interspeech",
        "iclr",
        "icml",
        "neurips",
        "aaai",
        "ijcai",
    )
    LISTING_URL_TOKENS = (
        "allconferencealert",
        "conferencealerts",
        "resurchify.com/e/conference",
        "/all-countries/",
        "/page/",
        "/events/",
        "/conferences/",
    )
    LOW_QUALITY_LISTING_HOSTS = {
        "allconferencealert.com",
        "conferencealerts.com",
        "resurchify.com",
    }
    SCHEDULE_FRAGMENT_TITLE_TOKENS = (
        "deadline",
        "due date",
        "submission",
        "metareview",
        "rebuttal",
        "notification",
        "camera-ready",
        "presenter",
        "program schedule",
        "faq",
        "frequently asked questions",
        "withdrawal",
        "commitment",
        "reviews submission",
    )
    SCHEDULE_FRAGMENT_PREFIXES = (
        "first call for workshop papers",
        "second call for workshop papers",
        "third call for papers",
    )
    GENERIC_EVENT_TITLE_VALUES = {
        "conference",
        "conferences",
        "events",
        "workshops",
        "tutorials",
        "publications",
        "program",
        "main conference",
        "welcome reception and social event",
    }
    NON_EVENT_TITLE_TOKENS = (
        "optional",
        "printing with on-site delivery",
        "presenter",
        "response to",
        "policies on",
        "registration cancellation",
        "faq",
        "frequently asked questions",
        "call for organizer nominations",
        "donation",
        "incident",
        "submission and style guidelines",
        "training",
        "certification",
        "bootcamp",
        "masterclass",
    )

    TYPE_MAP = {
        "conference": "conference",
        "workshop": "workshop",
        "seminar": "seminar",
        "call for papers": "call_for_papers",
        "hackathon": "hackathon",
    }

    DOMAIN_MAP = {
        "nlp": "nlp",
        "speech": "speech",
        "computer vision": "ai",
        "ai": "ai",
    }

    def __init__(self):
        super().__init__()
        self._extractor = LLMEventExtractor()
        try:
            self._search_client = TavilySearchClient()
        except Exception as exc:
            logger.warning("Tavily search client unavailable: %s", exc)
            self._search_client = None

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
        if self._search_client is None:
            self._log_error(
                "events_init_failed",
                "Tavily search client unavailable",
                source=self.name,
            )
            return

        search_client = self._search_client
        extractor = self._extractor

        target_items = max(
            1,
            min(
                self._to_int(getattr(SS, "EVENTS_MIN_ITEMS_PER_RUN", 10), 10),
                50,
            ),
        )
        batch_size = max(
            3,
            min(
                self._to_int(getattr(SS, "EVENTS_EXTRACTION_BATCH_SIZE", 8), 8),
                20,
            ),
        )
        max_batches = max(
            1,
            min(
                self._to_int(getattr(SS, "EVENTS_EXTRACTION_MAX_BATCHES", 8), 8),
                25,
            ),
        )

        search_queries = self._build_search_queries()
        if not search_queries:
            self._log_error(
                "events_query_build_failed",
                "No active or default search queries available",
                source=self.name,
            )
            return

        combined_results: list[dict] = []
        seen_urls: set[str] = set()
        rate_limit_hit = False
        rate_limit_message = ""
        max_results_per_query = max(
            3,
            min(
                self._to_int(getattr(SS, "EVENTS_TAVILY_MAX_RESULTS", 15), 15),
                30,
            ),
        )
        target_result_pool = max(60, target_items * 12)

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
                results = async_to_sync(search_client.search_events)(
                    query,
                    max_results=max_results_per_query,
                )
            except Exception as exc:
                self._log_error(
                    "events_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    result_url = self._safe_url(result.get("url"))
                    if not result_url or self._is_blocked_source_url(result_url):
                        continue
                    result_title = self._safe_text(result.get("title"))
                    result_content = self._safe_text(result.get("content"))
                    if not self._is_viable_search_result(
                        title=result_title,
                        content=result_content,
                        source_url=result_url,
                    ):
                        continue
                    if result_url in seen_urls:
                        continue
                    seen_urls.add(result_url)
                    combined_results.append(
                        {
                            "title": result_title,
                            "url": result_url,
                            "content": result_content,
                        }
                    )

            if len(combined_results) >= target_result_pool:
                break

        if not combined_results:
            logger.warning("No event search results returned by Tavily.")
            return

        candidates: list[dict] = []
        seen_candidate_keys: set[tuple[str, str, str]] = set()
        total_extraction_batches = min(
            max_batches,
            max(1, (len(combined_results) + batch_size - 1) // batch_size),
        )
        self.emit_progress(
            "extraction",
            0,
            total_extraction_batches,
            "🤖 Starting extraction...",
            current_item=f"Batch 0/{total_extraction_batches}",
        )

        for batch_index, offset in enumerate(
            range(0, len(combined_results), batch_size),
            start=1,
        ):
            if batch_index > max_batches:
                break

            batch_results = combined_results[offset : offset + batch_size]
            if not batch_results:
                continue

            self.emit_progress(
                "extraction",
                batch_index,
                total_extraction_batches,
                f"🤖 Extracting batch {batch_index}/{total_extraction_batches}",
                current_item=f"Batch {batch_index}/{total_extraction_batches}",
            )

            try:
                batch_candidates = async_to_sync(extractor.extract_events_from_search)(
                    batch_results
                )
            except Exception as exc:
                if self._is_groq_rate_limit_error(exc):
                    rate_limit_hit = True
                    rate_limit_message = str(exc)
                    logger.info(
                        "Groq rate limit encountered; continuing with fallback candidates"
                    )
                    break
                self._log_error(
                    "events_llm_extraction_failed",
                    str(exc),
                    source=self.name,
                )
                continue

            for candidate in batch_candidates or []:
                if not isinstance(candidate, dict):
                    continue
                if not self._is_viable_candidate(candidate):
                    continue
                candidate_key = self._candidate_dedupe_key(candidate)
                if candidate_key in seen_candidate_keys:
                    continue
                seen_candidate_keys.add(candidate_key)
                candidates.append(candidate)

        if not candidates:
            logger.info("No event candidates extracted from Tavily results.")
            fallback_candidates = self._build_fallback_candidates_from_search_results(
                combined_results,
                [],
                target_items,
            )
            if not fallback_candidates:
                return
            candidates = fallback_candidates

        if len(candidates) < target_items:
            fallback_candidates = self._build_fallback_candidates_from_search_results(
                combined_results,
                candidates,
                target_items,
            )
            if fallback_candidates:
                candidates.extend(fallback_candidates)

        if candidates:
            candidates = self._deduplicate_combined_candidates(candidates)

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            *get_auto_translate_fields(self.category),
        ]
        candidates = translator.batch_translate(candidates, fields=fields_to_translate)

        created_before = self.items_created
        updated_before = self.items_updated

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
                current_item=str(
                    candidate.get("title_en") or candidate.get("title") or ""
                ).strip(),
            )
            if not isinstance(candidate, dict):
                continue
            self._save_event_candidate(candidate)

        saved_count = (self.items_created - created_before) + (
            self.items_updated - updated_before
        )
        if rate_limit_hit and saved_count == 0:
            self._log_error(
                "groq_rate_limited",
                rate_limit_message or "Groq rate limit exceeded",
                source=self.name,
            )

        if saved_count < target_items:
            logger.warning(
                "Event scraper saved %s item(s), below configured target of %s",
                saved_count,
                target_items,
            )

    def _build_search_queries(self) -> list[str]:
        query_limit = max(
            3,
            min(
                self._to_int(getattr(SS, "EVENTS_SEARCH_QUERY_LIMIT", 14), 14),
                40,
            ),
        )
        current_year = timezone.now().date().year
        years = (current_year, current_year + 1)

        candidates: list[str] = []
        candidates.extend(self.get_active_search_queries(self.category))

        for template in self.DEFAULT_EVENT_SEARCH_QUERY_TEMPLATES:
            if "{year}" in template:
                for year in years:
                    candidates.append(template.format(year=year))
            else:
                candidates.append(template)

        deduped: list[str] = []
        seen: set[str] = set()
        for query in candidates:
            normalized = self._safe_text(query).strip()
            if not normalized:
                continue
            dedupe_key = normalized.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(normalized)

        return deduped[:query_limit]

    def _candidate_dedupe_key(self, candidate: dict) -> tuple[str, str, str]:
        title_key = self._safe_text(
            candidate.get("title_en") or candidate.get("title")
        ).lower()
        date_key = self._safe_text(candidate.get("start_date"))
        url_key = self._safe_text(
            candidate.get("source_url")
            or candidate.get("event_url")
            or candidate.get("website")
        ).lower()
        return (title_key, date_key, url_key)

    def _build_fallback_candidates_from_search_results(
        self,
        search_results: list[dict],
        existing_candidates: list[dict],
        target_items: int,
    ) -> list[dict]:
        existing_keys = {
            self._candidate_dedupe_key(candidate)
            for candidate in existing_candidates
            if isinstance(candidate, dict)
        }

        fallback_candidates: list[dict] = []
        max_needed = max(0, (target_items * 2) - len(existing_candidates))
        if max_needed <= 0:
            return fallback_candidates

        for row in search_results:
            if len(fallback_candidates) >= max_needed:
                break
            if not isinstance(row, dict):
                continue

            source_url = self._safe_url(row.get("url"))
            title_en = self._safe_text(row.get("title"))
            description_en = self._safe_text(row.get("content"))
            if not source_url or not title_en:
                continue
            if not self._is_viable_search_result(
                title=title_en,
                content=description_en,
                source_url=source_url,
            ):
                continue

            start_date = self._infer_start_date_from_text(
                f"{title_en}\n{description_en}"
            )
            if start_date is None:
                continue

            lowered = f"{title_en} {description_en}".lower()
            if "workshop" in lowered:
                event_type = "workshop"
            elif "seminar" in lowered:
                event_type = "seminar"
            elif "hackathon" in lowered:
                event_type = "hackathon"
            else:
                event_type = "conference"

            if "speech" in lowered or "asr" in lowered:
                domain = "speech"
            elif "vision" in lowered:
                domain = "computer_vision"
            elif "ai" in lowered or "artificial intelligence" in lowered:
                domain = "ai"
            else:
                domain = "nlp"

            candidate = {
                "title_en": title_en[:255],
                "title_ar": "",
                "description_en": (description_en or title_en)[:2000],
                "description_ar": "",
                "domain": domain,
                "event_type": event_type,
                "start_date": start_date.isoformat(),
                "end_date": start_date.isoformat(),
                "location": "Online",
                "website": source_url,
                "source_url": source_url,
                "source_name": "Tavily Search",
                "tags": ["events", domain, event_type],
            }
            if not self._is_viable_candidate(candidate):
                continue
            dedupe_key = self._candidate_dedupe_key(candidate)
            if dedupe_key in existing_keys:
                continue
            existing_keys.add(dedupe_key)
            fallback_candidates.append(candidate)

        return fallback_candidates

    def _infer_start_date_from_text(self, text: str):
        normalized = self._safe_text(text)
        if not normalized:
            return None

        iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", normalized)
        if iso_match:
            try:
                parsed = date(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3)),
                )
                if parsed >= timezone.now().date() - timedelta(days=30):
                    return parsed
            except ValueError:
                pass

        year_match = re.search(r"\b(20[2-4]\d)\b", normalized)
        if not year_match:
            return None

        try:
            year_value = int(year_match.group(1))
        except ValueError:
            return None

        current_year = timezone.now().date().year
        if year_value < current_year or year_value > (current_year + 4):
            return None

        return date(year_value, 6, 15)

    def _resolve_sources(self):
        return []

    def _is_high_quality_event_payload(
        self,
        payload: dict,
        search_results_blob: str,
        source_url: str,
    ) -> tuple[bool, str]:
        title = self._safe_text(payload.get("title_en"))
        description = self._safe_text(payload.get("description_en"))
        event_type = self._safe_text(
            payload.get("event_type") or payload.get("type")
        ).lower()
        start_date = self._parse_iso_date(payload.get("start_date"))

        if bool(getattr(SS, "EVENTS_REQUIRE_START_DATE", True)) and start_date is None:
            return False, "missing_start_date"

        if start_date is not None:
            today = timezone.now().date()
            if start_date < today - timedelta(days=30):
                return False, "event_too_old"
            if start_date > today + timedelta(days=int(SS.FRESHNESS_EVENTS)):
                return False, "event_too_far_future"

        if len(title) < 8:
            return False, "title_too_short"
        if self._is_generic_event_title(title):
            return False, "generic_title"
        if self._looks_like_non_event_title(title):
            return False, "non_event_title"
        if self._looks_like_listing_title(title):
            return False, "listing_title_detected"
        if self._looks_like_schedule_fragment_title(title):
            return False, "schedule_fragment_title"

        content_blob = f"{description}\n{search_results_blob[:2500]}"
        if self._looks_like_listing_body(content_blob):
            return False, "listing_body_detected"

        if not self._is_nlp_ai_relevant_payload(payload, title, description):
            return False, "irrelevant_topic"

        if payload.get("is_real_event") is False:
            return False, "llm_marked_non_event"

        confidence = payload.get("confidence")
        if isinstance(confidence, (float, int)):
            min_confidence = float(getattr(SS, "EVENTS_LLM_MIN_CONFIDENCE", 0.35))
            if float(confidence) < min_confidence:
                return False, "llm_confidence_too_low"

        signal_blob = f"{title} {description} {event_type}".lower()
        if not any(token in signal_blob for token in self.EVENT_SIGNAL_TOKENS):
            return False, "missing_event_signal"

        extracted_source_url = self._safe_text(payload.get("source_url"))
        if not extracted_source_url:
            return False, "missing_source_url"
        if self._looks_like_listing_url(extracted_source_url):
            return False, "listing_source_url"

        return True, ""

    def _looks_like_listing_url(self, url: str) -> bool:
        lowered = self._safe_text(url).lower()
        if not lowered:
            return False
        return any(token in lowered for token in self.LISTING_URL_TOKENS)

    def _looks_like_listing_title(self, title: str) -> bool:
        lowered = self._safe_text(title).lower()
        if not lowered:
            return False
        if self._is_generic_conference_listing_title(lowered):
            return True
        return any(pattern in lowered for pattern in self.LISTING_TITLE_PATTERNS)

    def _looks_like_listing_body(self, text: str) -> bool:
        lowered = self._safe_text(text).lower()
        if not lowered:
            return False
        return any(pattern in lowered for pattern in self.LISTING_BODY_PATTERNS)

    def _looks_like_schedule_fragment_title(self, title: str) -> bool:
        lowered = self._safe_text(title).lower()
        if not lowered:
            return False
        if any(token in lowered for token in self.SCHEDULE_FRAGMENT_TITLE_TOKENS):
            return True
        return any(
            lowered.startswith(prefix) for prefix in self.SCHEDULE_FRAGMENT_PREFIXES
        )

    def _is_generic_event_title(self, title: str) -> bool:
        normalized = self._safe_text(title).lower().strip()
        return normalized in self.GENERIC_EVENT_TITLE_VALUES

    def _is_generic_conference_listing_title(self, title: str) -> bool:
        lowered = self._safe_text(title).lower()
        if not lowered:
            return False

        if "conference overview" in lowered:
            return True
        if "conferences" not in lowered:
            return False
        if re.search(r"\bupcoming\b.*\bconferences\b", lowered):
            return True
        if re.search(r"\binternational\b.*\bconferences\b", lowered):
            return True
        if re.search(r"^list of .*\bconferences\b", lowered):
            return True
        if re.search(r"\bconferences\s+in\s+", lowered):
            return True

        has_year = bool(re.search(r"\b20[2-4]\d\b", lowered))
        has_known_event_code = any(
            code in lowered for code in self.TOPIC_RELEVANCE_EVENT_CODES
        )
        if has_year and not has_known_event_code:
            return True
        return False

    def _looks_like_non_event_title(self, title: str) -> bool:
        lowered = self._safe_text(title).lower()
        if not lowered:
            return False
        return any(token in lowered for token in self.NON_EVENT_TITLE_TOKENS)

    def _is_viable_search_result(
        self, title: str, content: str, source_url: str
    ) -> bool:
        if not self._safe_url(source_url):
            return False
        if self._is_blocked_source_url(source_url):
            return False
        if self._looks_like_listing_title(title):
            return False
        if self._looks_like_non_event_title(title):
            return False
        if self._looks_like_schedule_fragment_title(title):
            return False
        if self._looks_like_listing_body(content):
            return False

        signal_blob = f"{title} {content}".lower()
        if not any(token in signal_blob for token in self.EVENT_SIGNAL_TOKENS):
            return False
        return self._is_nlp_ai_relevant_payload({}, title, content)

    def _is_viable_candidate(self, candidate: dict) -> bool:
        if not isinstance(candidate, dict):
            return False

        title = self._safe_text(candidate.get("title_en") or candidate.get("title"))
        description = self._safe_text(
            candidate.get("description_en") or candidate.get("description")
        )
        source_url = self._safe_url(
            candidate.get("source_url")
            or candidate.get("event_url")
            or candidate.get("website")
        )
        if not self._is_viable_search_result(title, description, source_url):
            return False

        candidate_date = self._parse_iso_date(candidate.get("start_date"))
        return candidate_date is not None

    def _is_nlp_ai_relevant_payload(
        self, payload: dict, title: str, description: str
    ) -> bool:
        parts = [title, description]
        for key in (
            "domain",
            "domains",
            "research_domains",
            "keywords",
            "tags",
            "topic",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                parts.extend(self._safe_text(item) for item in value)
            else:
                parts.append(self._safe_text(value))

        blob = " ".join(part for part in parts if part).lower()
        if any(token in blob for token in self.TOPIC_RELEVANCE_TOKENS):
            return True

        normalized_blob = f" {blob} "
        return any(
            f" {code} " in normalized_blob for code in self.TOPIC_RELEVANCE_EVENT_CODES
        )

    def _is_low_quality_listing_source(self, source_url: str, source) -> bool:
        host = (urlparse((source_url or "").strip()).netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        if host not in self.LOW_QUALITY_LISTING_HOSTS:
            return False

        source_cfg = self._source_scrape_config(source)
        if source_cfg.get("allow_low_quality_listing_source") is True:
            return False
        return True

    def _map_extracted_payload_to_candidate(
        self,
        *,
        payload: dict,
        raw_text: str | None = None,
        source,
        source_name: str | None = None,
        source_url: str,
    ):
        del raw_text
        del source_name
        payload = dict(payload or {})

        title_en = self._safe_text(payload.get("title_en"))
        title_ar = self._safe_text(payload.get("title_ar")) or None

        description_en = self._safe_text(payload.get("description_en"))
        description_ar = self._safe_text(payload.get("description_ar")) or None

        location_value = self._safe_text(payload.get("location"))
        if not location_value:
            location_value = "Online"

        start_date = self._parse_iso_date(payload.get("start_date"))
        end_date = self._parse_iso_date(payload.get("end_date"))
        if start_date is not None and end_date is None:
            end_date = start_date

        website_url = self._safe_url(
            payload.get("event_url") or payload.get("source_url"),
            fallback=source_url,
        )
        registration_url = self._safe_url(
            payload.get("registration_link"),
            fallback=website_url,
        )

        event_type = self._normalize_model_event_type(
            payload.get("event_type") or payload.get("type")
        )
        domains = self._normalize_domains(
            payload.get("domain")
            or payload.get("domains")
            or payload.get("research_domains")
        )
        tags = self._normalize_tags(payload.get("keywords"), event_type, domains)
        if self._source_scrape_config(source).get("discovered"):
            tags = ["web_discovery", *tags]

        language = self._infer_language(
            title_en, title_ar, description_en, description_ar
        )
        is_online = location_value.lower() == "online"
        translation_status = infer_translation_status(
            raw_status=self._safe_text(payload.get("translation_status")) or "pending",
            english_values=[title_en, description_en],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "title": title_en,
            "title_en": title_en,
            "title_ar": title_ar,
            "description": description_en,
            "description_en": description_en,
            "description_ar": description_ar,
            "event_type": event_type,
            "domains": domains,
            "research_domains": domains,
            "location": location_value,
            "location_en": location_value,
            "location_ar": location_value,
            "start_date": start_date,
            "end_date": end_date,
            "submission_deadline": start_date if start_date is not None else None,
            "notification_date": start_date if start_date is not None else None,
            "website": website_url,
            "registration_link": registration_url,
            "is_online": is_online,
            "is_hybrid": False,
            "source_url": self._safe_url(
                payload.get("source_url"), fallback=source_url
            ),
            "source_name": self._safe_text(payload.get("source_name"))
            or self._source_name(source),
            "language": language,
            "tags": tags,
            "entities": {"keywords": tags},
            "contact_email": SCRAPER_BOT_EMAIL,
            "translation_status": translation_status,
            "priority_score": self._source_priority(source),
            "tier": self._source_tier(source),
            "extraction_confidence": payload.get("confidence"),
        }

    def _deduplicate_combined_candidates(self, candidates):
        deduped = []
        seen_keys = set()

        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                -(c.get("priority_score") or 0),
                c.get("source_name", ""),
                c.get("title_en", ""),
            ),
        )

        for item in sorted_candidates:
            title_key = self._normalize_text(
                item.get("title_en") or item.get("title", "")
            )
            date_key = str(item.get("start_date") or "")
            key = (title_key, date_key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)

        return deduped

    def _save_event_candidate(self, candidate_data: dict):
        from events.models import Event

        if not isinstance(candidate_data, dict):
            self.items_skipped += 1
            return

        title_en = self._safe_text(
            candidate_data.get("title_en") or candidate_data.get("title")
        )
        start_date = self._parse_iso_date(candidate_data.get("start_date"))

        if not title_en or start_date is None:
            self.items_skipped += 1
            return

        defaults = dict(candidate_data)
        defaults["title_en"] = title_en[:255]
        defaults.setdefault("title", title_en[:255])
        defaults["start_date"] = start_date
        defaults["end_date"] = (
            self._parse_iso_date(defaults.get("end_date")) or start_date
        )

        defaults.setdefault(
            "description",
            self._safe_text(
                defaults.get("description_en") or defaults.get("description")
            ),
        )
        defaults.setdefault("description_en", defaults.get("description") or "")

        if defaults.get("domain") and not defaults.get("domains"):
            defaults["domains"] = self._safe_text(defaults.get("domain")) or "nlp"

        defaults.setdefault(
            "website",
            self._safe_text(
                defaults.get("website")
                or defaults.get("event_url")
                or defaults.get("source_url")
            )
            or "",
        )
        defaults.setdefault("event_type", "conference")
        defaults.setdefault("source_name", self.name)

        defaults = self._ensure_event_fields(defaults)
        if not self.passes_min_confidence_to_save(defaults):
            self.items_skipped += 1
            return

        is_valid, reject_reason = self._passes_hard_event_rules(defaults)
        if not is_valid:
            logger.info("Skipping low quality event candidate: %s", reject_reason)
            self.items_skipped += 1
            return

        defaults.setdefault("contact_email", SCRAPER_BOT_EMAIL)
        defaults.setdefault("created_by", self.get_system_user())

        if not defaults.get("organizer"):
            organizer = self._resolve_organizer(defaults)
            if organizer is None:
                self.items_skipped += 1
                return
            defaults["organizer"] = organizer

        allowed_fields = {field.name for field in Event._meta.concrete_fields}
        defaults = {
            key: value for key, value in defaults.items() if key in allowed_fields
        }

        try:
            event, created = Event.objects.update_or_create(
                title_en=title_en[:255],
                start_date=start_date,
                defaults=defaults,
            )
        except Exception as exc:
            self.errors.append(f"Failed to upsert event '{title_en}': {exc}")
            return

        forced_updates = {}
        if event.approval_status != "pending":
            forced_updates["approval_status"] = "pending"
        if event.source != "scrape":
            forced_updates["source"] = "scrape"
        if forced_updates:
            Event.objects.filter(pk=event.pk).update(**forced_updates)

        self._attach_event_media(event, candidate_data)

        if created:
            self.items_created += 1
        else:
            self.items_updated += 1

        self.results.append(
            {
                "title": defaults.get("title_en", ""),
                "description": self.truncate(
                    self._safe_text(
                        defaults.get("description_en") or defaults.get("description")
                    ),
                    400,
                ),
                "type": defaults.get("event_type", "conference"),
                "url": defaults.get("website", ""),
                "location": defaults.get("location_en") or defaults.get("location", ""),
                "title_en": defaults.get("title_en", ""),
                "title_ar": defaults.get("title_ar") or None,
                "description_en": defaults.get("description_en")
                or defaults.get("description")
                or "",
                "description_ar": defaults.get("description_ar") or None,
                "start_date": defaults.get("start_date"),
                "end_date": defaults.get("end_date"),
                "website": defaults.get("website", ""),
                "location_en": defaults.get("location_en")
                or defaults.get("location", ""),
                "translation_status": candidate_data.get(
                    "translation_status", "pending"
                ),
            }
        )

    def _attach_event_media(self, event, candidate_data: dict) -> None:
        from scraping.file_downloader import (
            attach_file_to_model,
            try_download_document,
            try_download_image,
        )

        if not self._is_download_enabled():
            return

        item_name = self._safe_text(
            candidate_data.get("title_en") or candidate_data.get("title")
        )[:120]
        allowed_domains = self._collect_allowed_domains(candidate_data)

        if not getattr(event, "attachment", None):
            doc_urls = self._collect_candidate_document_urls(candidate_data)
            if doc_urls:
                doc_content, doc_filename = try_download_document(
                    doc_urls,
                    self.category,
                    item_name=item_name,
                    allowed_domains=allowed_domains,
                )
                if doc_filename:
                    attach_file_to_model(
                        event,
                        "attachment",
                        doc_content,
                        doc_filename,
                    )

        if not getattr(event, "banner_image", None):
            image_urls = self._collect_candidate_image_urls(candidate_data)
            if image_urls:
                image_content, image_filename = try_download_image(
                    image_urls,
                    self.category,
                    item_name=item_name,
                    allowed_domains=allowed_domains,
                )
                if image_filename:
                    attach_file_to_model(
                        event,
                        "banner_image",
                        image_content,
                        image_filename,
                    )

    def _collect_candidate_document_urls(self, candidate_data: dict) -> list[str]:
        urls: list[str] = []

        for key in ("attachment_url", "pdf_url", "file_url", "attachment"):
            urls.extend(self._coerce_url_list(candidate_data.get(key)))

        for key in ("event_url", "source_url", "website", "registration_link"):
            maybe_url = self._safe_url(candidate_data.get(key))
            if maybe_url and self._is_probable_pdf_url(maybe_url):
                urls.append(maybe_url)

        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            clean = self._safe_url(url)
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)

        return deduped

    def _collect_candidate_image_urls(self, candidate_data: dict) -> list[str]:
        urls: list[str] = []
        for key in ("banner_image_url", "image_url", "thumbnail", "og_image"):
            urls.extend(self._coerce_url_list(candidate_data.get(key)))

        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            clean = self._safe_url(url)
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)

        return deduped

    def _collect_allowed_domains(self, candidate_data: dict) -> list[str]:
        domains: list[str] = []
        for key in ("source_url", "event_url", "website", "registration_link"):
            candidate_url = self._safe_url(candidate_data.get(key))
            if not candidate_url:
                continue
            hostname = (urlparse(candidate_url).hostname or "").strip().lower()
            if hostname:
                domains.append(hostname)

        deduped: list[str] = []
        seen: set[str] = set()
        for domain in domains:
            if domain in seen:
                continue
            seen.add(domain)
            deduped.append(domain)

        return deduped

    def _apply_event_updates(self, event, item_dict, organizer):
        changed_fields = []

        self._maybe_set_field(
            event, "title", item_dict.get("title_en", "")[:255], changed_fields
        )
        self._maybe_set_field(
            event, "title_en", item_dict.get("title_en", "")[:255], changed_fields
        )
        self._maybe_set_field(
            event, "title_ar", item_dict.get("title_ar", "")[:255], changed_fields
        )

        self._maybe_set_field(
            event,
            "description",
            item_dict.get("description_en", ""),
            changed_fields,
            text_prefix_limit=500,
        )
        self._maybe_set_field(
            event,
            "description_en",
            item_dict.get("description_en", ""),
            changed_fields,
            text_prefix_limit=500,
        )
        self._maybe_set_field(
            event,
            "description_ar",
            item_dict.get("description_ar", ""),
            changed_fields,
            text_prefix_limit=500,
        )

        self._maybe_set_field(
            event,
            "event_type",
            item_dict.get("event_type", "conference"),
            changed_fields,
        )
        self._maybe_set_field(
            event,
            "domains",
            item_dict.get("research_domains", "nlp,ai"),
            changed_fields,
        )

        self._maybe_set_field(
            event, "location", item_dict.get("location_en", "")[:255], changed_fields
        )
        self._maybe_set_field(
            event, "location_en", item_dict.get("location_en", "")[:255], changed_fields
        )
        self._maybe_set_field(
            event, "location_ar", item_dict.get("location_ar", "")[:255], changed_fields
        )

        self._maybe_set_field(
            event, "start_date", item_dict.get("start_date"), changed_fields
        )
        self._maybe_set_field(
            event, "end_date", item_dict.get("end_date"), changed_fields
        )
        self._maybe_set_field(
            event,
            "submission_deadline",
            item_dict.get("submission_deadline"),
            changed_fields,
        )
        self._maybe_set_field(
            event,
            "notification_date",
            item_dict.get("notification_date"),
            changed_fields,
        )

        self._maybe_set_field(
            event, "website", item_dict.get("website", ""), changed_fields
        )
        self._maybe_set_field(
            event,
            "registration_link",
            item_dict.get("registration_link"),
            changed_fields,
        )

        self._maybe_set_field(
            event, "is_online", bool(item_dict.get("is_online", False)), changed_fields
        )
        self._maybe_set_field(
            event, "is_hybrid", bool(item_dict.get("is_hybrid", False)), changed_fields
        )

        self._maybe_set_field(
            event, "source_url", item_dict.get("source_url"), changed_fields
        )
        self._maybe_set_field(
            event, "source_name", item_dict.get("source_name"), changed_fields
        )
        self._maybe_set_field(
            event, "language", item_dict.get("language") or "en", changed_fields
        )

        self._maybe_set_field(
            event, "tags", item_dict.get("tags") or None, changed_fields
        )
        self._maybe_set_field(
            event, "entities", item_dict.get("entities", {}), changed_fields
        )

        self._maybe_set_field(event, "organizer", organizer, changed_fields)
        self._maybe_set_field(
            event,
            "contact_email",
            item_dict.get("contact_email") or SCRAPER_BOT_EMAIL,
            changed_fields,
        )

        return self._save_if_changed(event, changed_fields)

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
                },
            )
        except Exception as exc:
            logger.debug("priority meta upsert failed event=%s err=%s", event.id, exc)

    def _ensure_event_fields(self, item_dict: dict) -> dict:
        normalized = dict(item_dict or {})

        source_name = self._safe_text(normalized.get("source_name")) or self.name
        source_url = self._safe_url(
            normalized.get("source_url") or normalized.get("website"),
            fallback="",
        )

        title_en = self._safe_text(
            normalized.get("title_en") or normalized.get("title")
        )
        title_ar = self._safe_text(normalized.get("title_ar")) or None

        description_en = self._safe_text(
            normalized.get("description_en") or normalized.get("description")
        )
        description_ar = self._safe_text(normalized.get("description_ar")) or None

        start_date = self._parse_iso_date(normalized.get("start_date"))
        end_date = self._parse_iso_date(normalized.get("end_date"))
        if start_date is not None and end_date is None:
            end_date = start_date

        location_value = self._safe_text(
            normalized.get("location_en")
            or normalized.get("location")
            or normalized.get("location_ar")
        )
        if not location_value:
            location_value = "Online"

        event_type = self._normalize_model_event_type(normalized.get("event_type"))
        domains = self._normalize_domains(
            normalized.get("research_domains") or normalized.get("domains")
        )

        tags = self._normalize_tags(normalized.get("tags"), event_type, domains)
        entities = normalized.get("entities")
        if not isinstance(entities, dict):
            entities = {}
        entities.setdefault("keywords", tags)

        normalized["title"] = title_en[:255]
        normalized["title_en"] = title_en[:255]
        normalized["title_ar"] = title_ar[:255] if title_ar else ""

        normalized["description"] = description_en
        normalized["description_en"] = description_en
        normalized["description_ar"] = description_ar or ""

        normalized["event_type"] = event_type
        normalized["domains"] = domains
        normalized["research_domains"] = domains

        normalized["location"] = location_value[:255]
        normalized["location_en"] = location_value[:255]
        normalized["location_ar"] = location_value[:255]

        normalized["start_date"] = start_date
        normalized["end_date"] = end_date

        normalized["submission_deadline"] = self._parse_iso_date(
            normalized.get("submission_deadline")
        )
        if normalized["submission_deadline"] is None and start_date is not None:
            normalized["submission_deadline"] = start_date

        normalized["notification_date"] = self._parse_iso_date(
            normalized.get("notification_date")
        )
        if normalized["notification_date"] is None and start_date is not None:
            normalized["notification_date"] = start_date

        normalized["website"] = self._safe_url(
            normalized.get("website"), fallback=source_url
        )
        normalized["registration_link"] = self._safe_url(
            normalized.get("registration_link"),
            fallback=normalized["website"],
        )

        normalized["source_url"] = source_url
        normalized["source_name"] = source_name[:120]

        normalized["is_online"] = bool(
            normalized.get("is_online", False)
            or normalized["location_en"].lower() == "online"
        )
        normalized["is_hybrid"] = bool(normalized.get("is_hybrid", False))

        normalized["language"] = self._normalize_language(
            normalized.get("language"),
            title_en=title_en,
            title_ar=title_ar,
            description_en=description_en,
            description_ar=description_ar,
        )

        normalized["tags"] = tags
        normalized["entities"] = entities

        normalized["contact_email"] = (
            self._safe_text(normalized.get("contact_email")) or SCRAPER_BOT_EMAIL
        )

        normalized["translation_status"] = infer_translation_status(
            raw_status=self._safe_text(normalized.get("translation_status"))
            or "pending",
            english_values=[
                normalized.get("title_en"),
                normalized.get("description_en"),
            ],
            arabic_values=[
                normalized.get("title_ar"),
                normalized.get("description_ar"),
            ],
        )

        if "priority_score" not in normalized:
            normalized["priority_score"] = EVENT_PRIORITY_SCORES["global"]

        return normalized

    def _passes_hard_event_rules(self, item_dict: dict) -> tuple[bool, str]:
        title = self._safe_text(item_dict.get("title_en") or item_dict.get("title"))
        description = self._safe_text(
            item_dict.get("description_en") or item_dict.get("description")
        )
        start_date = item_dict.get("start_date")
        website = self._safe_text(item_dict.get("website"))

        if not title:
            return False, "missing_title"
        if self._is_generic_event_title(title):
            return False, "generic_title"
        if self._looks_like_non_event_title(title):
            return False, "non_event_title"
        if self._looks_like_listing_title(title):
            return False, "listing_title_detected"
        if self._looks_like_schedule_fragment_title(title):
            return False, "schedule_fragment_title"

        if self._looks_like_listing_body(description):
            return False, "listing_body_detected"

        if bool(getattr(SS, "EVENTS_REQUIRE_START_DATE", True)) and start_date is None:
            return False, "missing_start_date"

        if isinstance(start_date, date):
            today = timezone.now().date()
            if start_date < today - timedelta(days=30):
                return False, "event_too_old"
            if start_date > today + timedelta(days=int(SS.FRESHNESS_EVENTS)):
                return False, "event_too_far_future"
        else:
            return False, "invalid_start_date"

        if not website:
            return False, "missing_website"
        if self._is_blocked_source_url(website):
            return False, "blocked_source_host"

        signal_blob = f"{title} {description}".lower()
        if not any(token in signal_blob for token in self.EVENT_SIGNAL_TOKENS):
            return False, "missing_event_signal"
        if not self._is_nlp_ai_relevant_payload({}, title, description):
            return False, "irrelevant_topic"

        return True, ""

    def _resolve_organizer(self, item_dict: dict):
        source_name = (
            self._safe_text(item_dict.get("organizer_name"))
            or self._safe_text(item_dict.get("source_name"))
            or "NLP Research Community"
        )
        source_url = self._safe_url(
            item_dict.get("source_url") or item_dict.get("website"), fallback=""
        )

        country = self.get_or_create_country("International", "XX")

        return self.get_or_create_institution(
            source_name,
            inst_type="Other",
            country=country,
            acronym=self._source_acronym(source_name),
            website=self._source_base_url(source_url),
        )

    def _source_acronym(self, source_name: str) -> str:
        sanitized = "".join(
            ch if (ch.isalpha() or ch.isspace()) else " "
            for ch in (source_name or "").upper()
        )
        tokens = [token for token in sanitized.split() if token]
        if not tokens:
            return "NLP"
        if len(tokens) == 1:
            return tokens[0][:10]
        return "".join(token[0] for token in tokens[:10])[:10]

    @staticmethod
    def _source_base_url(url: str) -> str:
        parsed = urlparse(url or "")
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _source_url(source) -> str:
        return (
            getattr(source, "url", "") or getattr(source, "base_url", "") or ""
        ).strip()

    @staticmethod
    def _source_name(source) -> str:
        return (
            getattr(source, "name", "Configured Source") or "Configured Source"
        ).strip()

    @staticmethod
    def _source_scrape_config(source) -> dict:
        return dict(getattr(source, "scrape_config", {}) or {})

    def _source_priority(self, source) -> int:
        return self._to_int(
            self._source_scrape_config(source).get("priority_score"),
            EVENT_PRIORITY_SCORES["global"],
        )

    def _source_tier(self, source) -> int:
        return self._to_int(self._source_scrape_config(source).get("tier"), 1)

    def _source_max_events(self, source) -> int:
        return self._to_int(
            self._source_scrape_config(source).get("max_results"),
            int(getattr(SS, "EVENTS_TAVILY_MAX_RESULTS", 10)),
        )

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _safe_text(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() == "null":
            return ""
        return text

    @staticmethod
    def _safe_url(value, fallback: str = "") -> str:
        text = EventScraper._safe_text(value)
        if not text:
            text = EventScraper._safe_text(fallback)
        if not text:
            return ""

        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""

        return text[:200]

    @staticmethod
    def _parse_iso_date(value):
        if value is None:
            return None
        if isinstance(value, date):
            return value

        text = EventScraper._safe_text(value)
        if not text:
            return None

        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    def _normalize_model_event_type(self, value) -> str:
        normalized = self._safe_text(value).lower()
        if normalized in self.TYPE_MAP:
            return self.TYPE_MAP[normalized]
        return "conference"

    def _normalize_domains(self, value) -> str:
        text = self._safe_text(value).lower()

        tokens = []
        if text:
            for part in text.split(","):
                cleaned = self._safe_text(part).lower()
                if not cleaned:
                    continue
                tokens.append(self.DOMAIN_MAP.get(cleaned, cleaned))

        if not tokens:
            tokens = ["nlp", "ai"]

        deduped = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)

        return ",".join(deduped)

    def _normalize_tags(self, keywords, event_type: str, domains: str) -> list[str]:
        tags = []

        if isinstance(keywords, list):
            for value in keywords:
                clean = self._safe_text(value)
                if clean:
                    tags.append(clean.lower())
        else:
            text = self._safe_text(keywords)
            if text:
                for value in text.split(","):
                    clean = self._safe_text(value)
                    if clean:
                        tags.append(clean.lower())

        tags.append("events")
        tags.append(event_type)

        for domain in domains.split(","):
            clean_domain = self._safe_text(domain).lower()
            if clean_domain:
                tags.append(clean_domain)

        deduped = []
        seen = set()
        for tag in tags:
            if tag in seen:
                continue
            seen.add(tag)
            deduped.append(tag)

        return deduped

    def _infer_language(
        self,
        title_en: str,
        title_ar: str,
        description_en: str,
        description_ar: str,
    ) -> str:
        if self._contains_arabic(title_ar) or self._contains_arabic(description_ar):
            return "ar"
        if self._contains_arabic(title_en) or self._contains_arabic(description_en):
            return "ar"
        return "en"

    def _normalize_language(
        self,
        value,
        *,
        title_en: str,
        title_ar: str,
        description_en: str,
        description_ar: str,
    ) -> str:
        normalized = self._safe_text(value).lower()
        if normalized in {"ar", "fr", "en", "other"}:
            return normalized
        return self._infer_language(title_en, title_ar, description_en, description_ar)

    @staticmethod
    def _contains_arabic(text: str) -> bool:
        return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))

    @staticmethod
    def _is_groq_rate_limit_error(exc: Exception) -> bool:
        message = str(exc or "").lower()
        if "groq_rate_limit" in message:
            return True
        if "groq" in message and "rate" in message and "limit" in message:
            return True
        if "groq" in message and "too many requests" in message:
            return True
        return "groq" in message and "429" in message

    def _is_blocked_source_url(self, url):
        host = (urlparse((url or "").strip()).netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host in self.BLOCKED_SOURCE_HOSTS
