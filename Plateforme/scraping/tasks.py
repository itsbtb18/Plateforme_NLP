"""
Celery tasks for the Web Scraping module.

Provides background execution of scrapers so the admin dashboard
returns immediately while scraping runs asynchronously.
"""

import logging
import time
from celery import shared_task
from django.utils import timezone

from .scrapers import get_scraper, CATEGORY_META
from .metrics import (
    scrape_runs_total,
    scrape_duration_seconds,
    scrape_items_total,
    scrape_source_duration_seconds,
    scrape_source_items_total,
    update_source_health_metrics,
    update_scrape_queue_lag_metrics,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="scraping.tasks.run_scraper_task", queue="scraping")
def run_scraper_task(self, category, run_id=None, user_id=None):
    """
    Execute a scraper in the background and update the ScrapingRun record.

    Args:
        category: One of the CATEGORY_META keys (events, tools, news, courses, institutions).
        run_id: UUID (as string) of the ScrapingRun record to update. If None, one is created.
        user_id: ID of the user who triggered the run (optional, for scheduled tasks).
    """
    from .models import ScrapingRun

    started_at = time.monotonic()
    category_tier = str(CATEGORY_META.get(category, {}).get("tier", 4))

    # Resolve or create the ScrapingRun record
    run = None
    if run_id:
        try:
            run = ScrapingRun.objects.get(pk=run_id)
        except ScrapingRun.DoesNotExist:
            logger.warning("ScrapingRun %s not found, creating new one", run_id)

    if run is None:
        triggered_by = None
        if user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            triggered_by = User.objects.filter(pk=user_id).first()

        run = ScrapingRun.objects.create(
            category=category,
            status="running",
            triggered_by=triggered_by,
        )

    # Store celery task ID on the run
    run.task_id = self.request.id
    run.status = "running"
    run.save(update_fields=["task_id", "status"])

    if category not in CATEGORY_META:
        run.status = "failed"
        run.errors = f"Unknown category: {category}"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "errors", "completed_at"])
        scrape_runs_total.labels(category=category, status="failed").inc()
        scrape_duration_seconds.labels(category=category).observe(
            time.monotonic() - started_at
        )
        scrape_source_duration_seconds.labels(
            category=category,
            source_name="all_sources",
            source_tier=category_tier,
        ).observe(time.monotonic() - started_at)
        update_scrape_queue_lag_metrics(force=True)
        return {"status": "error", "message": run.errors}

    try:
        scraper = get_scraper(category)
        result = scraper.run()

        run.items_found = result.get("items_found", 0)
        run.items_created = result.get("items_created", 0)
        run.items_skipped = result.get("items_skipped", 0)
        run.errors = "\n".join(result.get("errors", []))
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save()

        scrape_runs_total.labels(category=category, status="success").inc()
        scrape_duration_seconds.labels(category=category).observe(
            time.monotonic() - started_at
        )
        scrape_source_duration_seconds.labels(
            category=category,
            source_name="all_sources",
            source_tier=category_tier,
        ).observe(time.monotonic() - started_at)
        scrape_items_total.labels(category=category, outcome="found").inc(
            run.items_found
        )
        scrape_items_total.labels(category=category, outcome="created").inc(
            run.items_created
        )
        scrape_items_total.labels(category=category, outcome="skipped").inc(
            run.items_skipped
        )
        if run.items_created:
            scrape_source_items_total.labels(
                category=category,
                source_name="all_sources",
                outcome="saved",
            ).inc(run.items_created)
        if run.items_skipped:
            scrape_source_items_total.labels(
                category=category,
                source_name="all_sources",
                outcome="skipped_dedup",
            ).inc(run.items_skipped)
        update_source_health_metrics(category=category)
        update_scrape_queue_lag_metrics(force=True)

        logger.info(
            "scrape_run_completed",
            extra={
                "category": category,
                "source_name": "all_sources",
                "items_created": run.items_created,
                "items_skipped": run.items_skipped,
                "items_found": run.items_found,
                "task_id": self.request.id,
                "run_id": str(run.pk),
            },
        )

        return {
            "status": "success",
            "run_id": str(run.pk),
            "items_found": run.items_found,
            "items_created": run.items_created,
            "items_skipped": run.items_skipped,
            "errors": result.get("errors", []),
            "results": result.get("results", []),
            "duration": run.duration,
        }

    except Exception as exc:
        run.status = "failed"
        run.errors = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "errors", "completed_at"])

        scrape_runs_total.labels(category=category, status="failed").inc()
        scrape_duration_seconds.labels(category=category).observe(
            time.monotonic() - started_at
        )
        scrape_source_duration_seconds.labels(
            category=category,
            source_name="all_sources",
            source_tier=category_tier,
        ).observe(time.monotonic() - started_at)
        scrape_source_items_total.labels(
            category=category,
            source_name="all_sources",
            outcome="skipped_error",
        ).inc(1)
        update_source_health_metrics(category=category)
        update_scrape_queue_lag_metrics(force=True)

        logger.exception(
            "scrape_run_failed",
            extra={
                "category": category,
                "source_name": "all_sources",
                "task_id": self.request.id,
                "run_id": str(run.pk),
            },
        )
        raise  # Re-raise so Celery marks the task as FAILURE
