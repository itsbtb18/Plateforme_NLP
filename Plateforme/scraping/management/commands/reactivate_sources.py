from django.core.management.base import BaseCommand

from scraping.models import ScrapingSource


class Command(BaseCommand):
    help = "Reactivate quarantined scraping sources and reset failure counters."

    def handle(self, *args, **options):
        sources = ScrapingSource.objects.filter(is_active=False)
        count = sources.count()
        sources.update(
            is_active=True,
            fail_count=0,
            last_error="",
        )
        self.stdout.write(
            self.style.SUCCESS(f"Reactivated {count} scraping source(s).")
        )
