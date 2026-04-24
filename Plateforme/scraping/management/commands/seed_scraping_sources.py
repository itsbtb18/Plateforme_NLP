import json
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from scraping.models import ScrapingSource

logger = logging.getLogger(__name__)

CANONICAL_CATEGORIES = [
    "events",
    "tools",
    "courses",
    "news",
    "opportunities",
    "corpus",
]

SECTION_TO_CATEGORY = {
    "events": "events",
    "tools": "tools",
    "courses": "courses",
    "news": "news",
    "opportunities": "opportunities",
    "corpus": "corpus",
    # Legacy mappings.
    "institutions": "opportunities",
    "datasets": "corpus",
    "papers": "news",
    "rss": "news",
}

SCRAPER_TYPE_TO_SOURCE_TYPE = {
    "api": "api",
    "html": "web",
    "rss": "web",
    "web": "web",
}


class Command(BaseCommand):
    help = "Seed scraping sources from fixtures/default_sources.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reseed even if sources already exist",
        )
        parser.add_argument(
            "--append",
            action="store_true",
            help="Add new sources from fixture, skip existing URLs",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete all sources and reseed from fixture",
        )

    def handle(self, *args, **options):
        force = options["force"]
        append = options["append"]
        replace = options["replace"]

        if replace:
            count, _ = ScrapingSource.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing sources."))
        elif not append and not force and ScrapingSource.objects.exists():
            self.stdout.write(
                self.style.WARNING("ScrapingSource table is not empty. Seed skipped.")
            )
            return

        fixture_path = (
            Path(settings.BASE_DIR) / "scraping" / "fixtures" / "default_sources.json"
        )
        if not fixture_path.exists():
            self.stdout.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
            return

        with fixture_path.open("r", encoding="utf-8") as handle:
            sources_data = json.load(handle)

        if not isinstance(sources_data, list):
            self.stdout.write(self.style.ERROR("Fixture must contain a JSON array."))
            return

        existing_by_key = {
            (row.category, (row.url or "").strip()): row
            for row in ScrapingSource.objects.all()
        }

        created = 0
        updated = 0
        skipped = 0

        for data in sources_data:
            if not isinstance(data, dict):
                skipped += 1
                continue

            section = str(data.get("section", "")).strip().lower()
            category = SECTION_TO_CATEGORY.get(section)
            if category is None:
                logger.error(
                    "Unknown section '%s' in fixture. Valid sections: %s",
                    section,
                    sorted(SECTION_TO_CATEGORY.keys()),
                )
                self.stderr.write(f"Skipping unknown section: {section}")
                skipped += 1
                continue

            url = data.get("url", "").strip()

            if not url:
                skipped += 1
                continue

            key = (category, url)
            existing = existing_by_key.get(key)

            if append and existing is not None:
                skipped += 1
                continue

            payload = {
                "category": category,
                "name": data.get("name", ""),
                "url": url,
                "base_url": url,
                "source_type": SCRAPER_TYPE_TO_SOURCE_TYPE.get(
                    str(data.get("scraper_type", "web")).strip().lower(),
                    "web",
                ),
                "is_active": bool(data.get("is_active", True)),
                "is_default": bool(data.get("is_default", True)),
                "description": data.get("notes", ""),
                "scrape_config": {
                    "tier": int(data.get("tier", 1) or 1),
                    "country": data.get("country", "global"),
                    "schedule_cron": data.get("schedule_cron", "0 6 * * *"),
                    "selectors": {
                        "title": data.get("selector_title", ""),
                        "body": data.get("selector_body", ""),
                        "date": data.get("selector_date", ""),
                        "author": data.get("selector_author", ""),
                    },
                },
            }

            if existing is not None:
                if force or replace:
                    for field_name, value in payload.items():
                        setattr(existing, field_name, value)
                    existing.save()
                    updated += 1
                else:
                    skipped += 1
                continue

            ScrapingSource.objects.create(**payload)
            created += 1

        summary = (
            f"Seed complete: created={created}, updated={updated}, skipped={skipped}."
        )
        if created or updated:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(self.style.WARNING(summary))
