from __future__ import annotations

import json
import logging
from datetime import timedelta
from uuid import UUID

from django.utils import timezone
from django.utils.text import slugify

logger = logging.getLogger(__name__)


class AdaptiveScheduler:
    """Compute and apply per-source adaptive scraping schedules."""

    TIERS = {
        "very_high": 6 * 3600,
        "high": 12 * 3600,
        "medium": 24 * 3600,
        "low": 3 * 24 * 3600,
        "dormant": 7 * 24 * 3600,
    }

    def __init__(self, lookback_runs: int = 30):
        self.lookback_runs = lookback_runs

    def compute_optimal_interval(self, source_id: str | UUID) -> tuple[str, int]:
        """
        Analyze last N completed runs for a source.

        Returns:
            tuple[tier_name, interval_seconds]
        """
        from .models import ScrapingRun

        runs = list(
            ScrapingRun.objects.filter(
                source_id=source_id,
                status="completed",
            ).order_by("-started_at")[: self.lookback_runs]
        )

        if len(runs) < 3:
            return ("medium", self.TIERS["medium"])

        total_new_items = sum(int(run.items_created or 0) for run in runs)

        oldest_run = runs[-1]
        newest_run = runs[0]
        span_seconds = (newest_run.started_at - oldest_run.started_at).total_seconds()
        days_covered = max(span_seconds / 86400.0, 1.0)

        items_per_day = total_new_items / days_covered

        if items_per_day > 1.0:
            tier = "very_high"
        elif items_per_day > 0.33:
            tier = "high"
        elif items_per_day > 0.14:
            tier = "medium"
        elif items_per_day > 0.03:
            tier = "low"
        else:
            tier = "dormant"

        return (tier, self.TIERS[tier])

    def update_source_schedule(self, source_id: str | UUID) -> dict:
        """Update or create django-celery-beat schedule entry for a source."""
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        from .models import ScrapingSource

        source = ScrapingSource.objects.get(id=source_id)
        previous_tier = source.schedule_tier
        previous_interval = source.schedule_interval_hours

        tier, interval_seconds = self.compute_optimal_interval(source_id)
        interval_hours = max(interval_seconds // 3600, 1)

        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=interval_hours,
            period=IntervalSchedule.HOURS,
        )

        task_name = f"scraping_{slugify(source.name) or source_id}"
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "interval": schedule,
                "task": "scraping.tasks.run_scraper_task",
                "kwargs": json.dumps({"source_id": str(source_id)}),
                "enabled": source.is_active,
            },
        )

        source.schedule_tier = tier
        source.schedule_interval_hours = interval_hours
        source.schedule_updated_at = timezone.now()
        source.save(
            update_fields=[
                "schedule_tier",
                "schedule_interval_hours",
                "schedule_updated_at",
            ]
        )

        logger.info(
            "[AdaptiveScheduler] %s: tier=%s interval=%sh (was %sh)",
            source.name,
            tier,
            interval_hours,
            previous_interval,
        )

        return {
            "source": source.name,
            "previous_tier": previous_tier,
            "new_tier": tier,
            "new_interval_hours": interval_hours,
        }

    def update_all_sources(self) -> list[dict]:
        """Recompute schedules for all active sources."""
        from django_celery_beat.models import PeriodicTask

        from .models import ScrapingSource

        # Replace legacy fixed category schedules with adaptive per-source schedules.
        PeriodicTask.objects.filter(
            name__in=[
                "Auto-scrape News Daily",
                "Auto-scrape Events Weekly",
                "Auto-scrape Tools Weekly",
                "Auto-scrape Courses Monthly",
                "Auto-scrape Institutions Monthly",
            ]
        ).update(enabled=False)

        sources = ScrapingSource.objects.filter(is_active=True).order_by(
            "category", "name"
        )
        return [self.update_source_schedule(source.id) for source in sources]

    def estimate_items_per_day(self, source_id: str | UUID) -> float:
        """Estimate items/day from recent completed runs for admin display."""
        from .models import ScrapingRun

        since = timezone.now() - timedelta(days=90)
        runs = list(
            ScrapingRun.objects.filter(
                source_id=source_id,
                status="completed",
                started_at__gte=since,
            ).order_by("-started_at")[: self.lookback_runs]
        )
        if len(runs) < 2:
            return 0.0

        total = sum(int(run.items_created or 0) for run in runs)
        span_seconds = (runs[0].started_at - runs[-1].started_at).total_seconds()
        days = max(span_seconds / 86400.0, 1.0)
        return round(total / days, 2)
