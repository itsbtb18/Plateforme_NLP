from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import IntegrityError
from django.utils import timezone
from events.models import Event
from institutions.models import Country, Institution

from scraping.base_scraper import BaseEventScraper, StandardEvent
from scraping.confportal_scraper import ConfPortalScraper
from scraping.deduplicator import EventDeduplicator
from scraping.validator import EventValidator
from scraping.wikicfp_scraper import WikiCFPScraper

logger = logging.getLogger(__name__)


class ConferenceAlertsScraper(ConfPortalScraper):
    source_name = "Conference Alerts"
    base_url = "https://www.conferencealerts.com"


class AllConferencesScraper(ConfPortalScraper):
    source_name = "All Conferences"
    base_url = "https://allconferencealert.net"


class NatureEventsScraper(ConfPortalScraper):
    source_name = "Nature Events"
    base_url = "https://www.nature.com/naturecareers/events"


class IEEEConferencesScraper(ConfPortalScraper):
    source_name = "IEEE Conferences"
    base_url = "https://conferences.ieee.org/conferences_events/conferences/search"


class EventScraperManager:
    """Run multiple source scrapers with strict fault tolerance."""

    def __init__(self, run_id: str | None = None, max_workers: int = 6) -> None:
        self.run_id = run_id
        self.max_workers = max_workers
        self.validator = EventValidator()
        self.deduplicator = EventDeduplicator()

        self.scrapers: list[BaseEventScraper] = [
            WikiCFPScraper(),
            ConferenceAlertsScraper(),
            AllConferencesScraper(),
            ConfPortalScraper(),
            NatureEventsScraper(),
            IEEEConferencesScraper(),
        ]

    def run(self) -> dict[str, Any]:
        self._ws(status="scraping", source="starting")

        source_results: dict[str, list[StandardEvent]] = {}
        source_failures: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(self._safe_scrape, scraper): scraper
                for scraper in self.scrapers
            }
            for future in as_completed(future_map):
                scraper = future_map[future]
                events, error = future.result()
                if error:
                    source_failures[scraper.source_name] = error
                    logger.warning(
                        "[SCRAPER] %s -> FAILED (%s)", scraper.source_name, error
                    )
                else:
                    source_results[scraper.source_name] = events
                    logger.info(
                        "[SCRAPER] %s -> %s events found",
                        scraper.source_name,
                        len(events),
                    )

        all_events: list[StandardEvent] = []
        for events in source_results.values():
            all_events.extend(events)

        if not all_events and source_failures:
            logger.error("[TOTAL] 0 events saved (all sources failed)")
            self._ws(status="completed", created=0, skipped=len(source_failures))
            return {
                "created": 0,
                "skipped": len(source_failures),
                "errors": source_failures,
                "all_sources_failed": True,
            }

        self._ws(status="parsing")

        valid, invalid = self.validator.validate_many(all_events)
        deduped, duplicate_count = self.deduplicator.deduplicate(valid)

        self._ws(status="saving")

        created_count, db_duplicates, save_errors = self._save_events(deduped)
        skipped_total = (
            len(invalid) + duplicate_count + db_duplicates + len(save_errors)
        )

        logger.info(
            "[DATABASE] %s created, %s duplicates",
            created_count,
            duplicate_count + db_duplicates,
        )
        logger.info("[TOTAL] %s events saved", created_count)

        self._ws(status="completed", created=created_count, skipped=skipped_total)

        return {
            "created": created_count,
            "skipped": skipped_total,
            "invalid": len(invalid),
            "duplicates": duplicate_count + db_duplicates,
            "save_errors": save_errors,
            "source_failures": source_failures,
            "source_counts": {k: len(v) for k, v in source_results.items()},
        }

    def _safe_scrape(
        self, scraper: BaseEventScraper
    ) -> tuple[list[StandardEvent], str | None]:
        self._ws(status="scraping", source=scraper.source_name)
        try:
            return scraper.scrape(), None
        except Exception as exc:
            return [], type(exc).__name__

    def _save_events(self, events: list[StandardEvent]) -> tuple[int, int, list[str]]:
        created = 0
        duplicates = 0
        errors: list[str] = []

        organizer = self._get_default_organizer()
        created_by = self._get_default_user()

        for event in events:
            try:
                exists = Event.objects.filter(
                    title__iexact=event.title.strip(),
                    start_date=event.start_date.date(),
                ).exists()
                if exists:
                    duplicates += 1
                    continue

                end_date = (
                    event.end_date.date() if event.end_date else event.start_date.date()
                )
                deadline = event.deadline.date() if event.deadline else None

                Event.objects.create(
                    title=event.title[:255],
                    title_en=event.title[:255],
                    title_ar=event.title[:255],
                    description=event.description or event.title,
                    description_en=event.description or event.title,
                    description_ar=event.description or event.title,
                    event_type="conference",
                    domains="nlp,ai",
                    location=event.location[:255] if event.location else "Unknown",
                    location_en=event.location[:255] if event.location else "Unknown",
                    location_ar=event.location[:255] if event.location else "Unknown",
                    start_date=event.start_date.date(),
                    end_date=end_date,
                    submission_deadline=deadline,
                    website=event.url,
                    source_url=event.url,
                    source_name=event.source,
                    language="en",
                    tags=["pipeline_v2", "auto_scraped"],
                    organizer=organizer,
                    contact_email="scraper-bot@nlp-platform.local",
                    approval_status="pending",
                    created_by=created_by,
                    source="scrape",
                )
                created += 1
            except IntegrityError:
                duplicates += 1
            except Exception as exc:
                reason = f"{event.source}:{event.title[:60]}:{type(exc).__name__}"
                errors.append(reason)
                logger.warning("[DATABASE] save_failed reason=%s", reason)
                continue

        return created, duplicates, errors

    def _get_default_organizer(self) -> Institution:
        country, _ = Country.objects.get_or_create(
            code="XX",
            defaults={"name_en": "International", "name_ar": "International"},
        )
        organizer, _ = Institution.objects.get_or_create(
            name="NLP Scraper Bot",
            defaults={
                "name_en": "NLP Scraper Bot",
                "name_ar": "NLP Scraper Bot",
                "type": "Other",
                "country": country,
                "city": "Online",
                "city_en": "Online",
                "city_ar": "Online",
                "website": "https://example.local/scraper",
                "email": "scraper-bot@nlp-platform.local",
                "description": "Auto-generated organizer for scraping pipeline",
                "description_en": "Auto-generated organizer for scraping pipeline",
                "description_ar": "Auto-generated organizer for scraping pipeline",
            },
        )
        return organizer

    def _get_default_user(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        existing = (
            user_model.objects.filter(is_staff=True).first()
            or user_model.objects.first()
        )
        if existing is not None:
            return existing

        # Fallback creation for custom user models with common required fields.
        defaults = {
            "email": "scraper-bot@nlp-platform.local",
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
        }
        for field_name in ["full_name_en", "full_name_ar", "username"]:
            if field_name in {f.name for f in user_model._meta.fields}:
                defaults[field_name] = "Scraper Bot"

        user = user_model(**defaults)
        user.set_password("scraper-bot-password")
        user.save()
        return user

    def _ws(self, **payload: Any) -> None:
        if not self.run_id:
            return

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        message = {
            "type": "status_update",
            "status": payload.get("status", "scraping"),
            "source": payload.get("source", ""),
            "created": int(payload.get("created", 0)),
            "skipped": int(payload.get("skipped", 0)),
            "progress": int(payload.get("progress", 0)),
            "total": int(payload.get("total", 0)),
            "timestamp": timezone.now().isoformat(),
            "message": payload.get("status", "scraping"),
            "items_scraped": int(payload.get("created", 0)),
            "items_failed": int(payload.get("skipped", 0)),
            "current_source": payload.get("source", ""),
        }

        async_to_sync(channel_layer.group_send)(f"scraping_{self.run_id}", message)

    @staticmethod
    def serialize_events(events: list[StandardEvent]) -> list[dict[str, Any]]:
        serializable: list[dict[str, Any]] = []
        for event in events:
            payload = asdict(event)
            payload["start_date"] = (
                event.start_date.isoformat() if event.start_date else None
            )
            payload["end_date"] = event.end_date.isoformat() if event.end_date else None
            payload["deadline"] = event.deadline.isoformat() if event.deadline else None
            serializable.append(payload)
        return serializable
