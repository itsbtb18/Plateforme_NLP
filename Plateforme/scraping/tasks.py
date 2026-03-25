"""
Celery tasks for the Web Scraping module.

Provides background execution of scrapers so the admin dashboard
returns immediately while scraping runs asynchronously.
"""

import logging
import time
from typing import Any

from celery import shared_task
from django.utils import timezone

from .dead_letter import record_dead_letter
from .metrics import (
    scrape_duration_seconds,
    scrape_items_total,
    scrape_runs_total,
    scrape_source_duration_seconds,
    scrape_source_items_total,
    update_scrape_queue_lag_metrics,
    update_source_health_metrics,
)
from .scrapers import CATEGORY_META, get_scraper

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="scraping.tasks.run_scraper_task", queue="scraping")
def run_scraper_task(
    self,
    category: str,
    run_id: str | None = None,
    allow_run_recreate: bool = False,
    user_id: int | None = None,
) -> dict[str, Any]:
    """
    Execute a scraper in the background and update the ScrapingRun record.

    Args:
        category: One of the CATEGORY_META keys (events, tools, news, courses, institutions).
        run_id: UUID string of the ScrapingRun record to update. If ``None``, one is created.
        allow_run_recreate: Recreate a missing run when ``run_id`` does not exist.
        user_id: Optional user id that triggered the run.

    Returns:
        dict[str, Any]: Status payload containing run id, counters, and errors.

    Raises:
        ValueError: If ``run_id`` is missing and recreation is disabled.
        Exception: Re-raises scraper failures so Celery marks the task as failed.
    """
    from .models import ScrapingRun

    started_at = time.monotonic()
    category_tier = str(CATEGORY_META.get(category, {}).get("tier", 4))

    # Resolve or create the ScrapingRun record
    triggered_by = None
    if user_id:
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        triggered_by = user_model.objects.filter(pk=user_id).first()

    if run_id:
        try:
            run = ScrapingRun.objects.get(id=run_id)
        except ScrapingRun.DoesNotExist as exc:
            if not allow_run_recreate:
                logger.error(
                    "run_id_not_found",
                    extra={
                        "run_id": run_id,
                        "category": category,
                        "task_id": self.request.id,
                    },
                )
                raise ValueError(
                    f"ScrapingRun {run_id} not found. "
                    f"Pass allow_run_recreate=True to create a new run."
                ) from exc
            logger.warning(
                "run_recreated", extra={"run_id": run_id, "category": category}
            )
            run = ScrapingRun.objects.create(
                category=category, status="running", triggered_by=triggered_by
            )
    else:
        run = ScrapingRun.objects.create(
            category=category, status="running", triggered_by=triggered_by
        )

    # Store celery task ID on the run
    run.task_id = self.request.id
    run.status = "running"
    run.save(update_fields=["task_id", "status"])

    logger.info(
        "scrape_task_started",
        extra={
            "category": category,
            "run_id": str(run.id),
            "task_id": self.request.id,
        },
    )

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
            "scrape_task_completed",
            extra={
                "category": category,
                "run_id": str(run.id),
                "items_saved": run.items_created,
                "items_skipped": run.items_skipped,
                "duration_seconds": (timezone.now() - run.started_at).total_seconds(),
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

        record_dead_letter(
            category=category,
            source_name="all_sources",
            item={"url": "unknown", "title": f"run_id={run.id}"},
            error=str(exc),
            retry_count=0,
        )

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

        logger.error(
            "scrape_task_failed",
            extra={
                "category": category,
                "run_id": str(run.id),
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        raise  # Re-raise so Celery marks the task as FAILURE
