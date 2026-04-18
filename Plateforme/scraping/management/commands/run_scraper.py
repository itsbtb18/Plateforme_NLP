"""
Management command: run_scraper
Usage:
    python manage.py run_scraper --category events
    python manage.py run_scraper --all
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.utils import timezone

from scraping.constants import ALL_CATEGORIES
from scraping.models import ScrapingRun
from scraping.scrapers import get_scraper


class Command(BaseCommand):
    help = "Run web scrapers to discover NLP resources from the web."

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            "-c",
            type=str,
            choices=list(ALL_CATEGORIES),
            help=f"Scraper category to run ({', '.join(ALL_CATEGORIES)})",
        )
        parser.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Run all scrapers",
        )
        parser.add_argument(
            "--skip-resource-sync",
            action="store_true",
            help="Skip syncing websites from website_to_add_to_scraping.md before running.",
        )

    def handle(self, *args, **options):
        if not options.get("skip_resource_sync"):
            try:
                call_command("sync_resource_websites")
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Resource website sync skipped due to error: {exc}"
                    )
                )

        categories = []
        if options.get("all"):
            categories = list(ALL_CATEGORIES)
        elif options.get("category"):
            categories = [options["category"]]
        else:
            raise CommandError(
                "Specify --category <name> or --all. "
                f"Available categories: {', '.join(ALL_CATEGORIES)}"
            )

        for cat in categories:
            self.stdout.write(self.style.HTTP_INFO(f"\n{'─' * 50}"))
            self.stdout.write(self.style.HTTP_INFO(f"  Running scraper: {cat}"))
            self.stdout.write(self.style.HTTP_INFO(f"{'─' * 50}"))

            run = ScrapingRun.objects.create(category=cat, status="running")

            try:
                scraper = get_scraper(cat)
                result = scraper.run()

                run.items_found = result.get("items_found", 0)
                run.items_created = result.get("items_created", 0)
                run.items_skipped = result.get("items_skipped", 0)
                run.errors = "\n".join(result.get("errors", []))
                run.status = "completed"
                run.completed_at = timezone.now()
                run.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {cat}: {run.items_created} created, "
                        f"{run.items_skipped} skipped, "
                        f"{len(result.get('errors', []))} errors"
                    )
                )

                for err in result.get("errors", []):
                    self.stdout.write(self.style.WARNING(f"    ⚠ {err}"))

            except Exception as exc:
                run.status = "failed"
                run.errors = str(exc)
                run.completed_at = timezone.now()
                run.save()
                self.stdout.write(self.style.ERROR(f"  ✗ {cat} FAILED: {exc}"))

        self.stdout.write(self.style.SUCCESS("\nAll done."))
