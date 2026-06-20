from django.core.management.base import BaseCommand

from scraping.constants import SCHEDULE_TABLE_NAME_WIDTH
from scraping.models import ScrapingSource


class Command(BaseCommand):
    help = "Show adaptive scraping schedules for all sources."

    def handle(self, *args, **options):
        rows = list(
            ScrapingSource.objects.order_by("name").values(
                "name",
                "category",
                "schedule_tier",
                "schedule_interval_hours",
                "schedule_updated_at",
            )
        )

        if not rows:
            self.stdout.write("No scraping sources found.")
            return

        name_width = SCHEDULE_TABLE_NAME_WIDTH
        header = f"{'Source Name':<{name_width}} | Category | Tier      | Interval | Last Updated"
        separator = (
            f"{'-' * name_width}|----------|-----------|----------|-------------"
        )
        self.stdout.write(header)
        self.stdout.write(separator)

        for row in rows:
            interval_hours = int(row.get("schedule_interval_hours") or 0)
            interval = (
                f"{interval_hours // 24}d"
                if interval_hours % 24 == 0 and interval_hours >= 24
                else f"{interval_hours}h"
            )
            updated = row.get("schedule_updated_at")
            updated_str = updated.date().isoformat() if updated else "-"
            self.stdout.write(
                f"{row['name'][:name_width]:<{name_width}} | "
                f"{row['category']:<8} | "
                f"{row['schedule_tier']:<9} | "
                f"{interval:<8} | "
                f"{updated_str}"
            )
