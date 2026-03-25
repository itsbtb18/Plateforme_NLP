"""
Management command: run_scraper
Usage:
    python manage.py run_scraper --category events
    python manage.py run_scraper --all
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from scraping.models import ScrapingRun
from scraping.scrapers import SCRAPERS, get_scraper


class Command(BaseCommand):
    help = "Run web scrapers to discover NLP resources from the web."

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            "-c",
            type=str,
            choices=list(SCRAPERS.keys()),
            help="Scraper category to run (events, tools, news, courses, institutions)",
        )
        parser.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Run all scrapers",
        )

    def handle(self, *args, **options):
        categories = []
        if options.get("all"):
            categories = list(SCRAPERS.keys())
        elif options.get("category"):
            categories = [options["category"]]
        else:
            raise CommandError(
                "Specify --category <name> or --all. "
                f"Available categories: {', '.join(SCRAPERS.keys())}"
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
