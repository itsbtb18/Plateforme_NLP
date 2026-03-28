"""
Celery tasks for the Web Scraping module.

Provides background execution of scrapers so the admin dashboard
returns immediately while scraping runs asynchronously.
"""

import logging
import time
from collections import Counter
from typing import Any

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from .constants import DEAD_LETTER_INITIAL_RETRY_COUNT, SCRAPING_CELERY_QUEUE
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
from .scraper_manager import EventScraperManager
from .scrapers import CATEGORY_META, get_scraper
from .validators import ContentValidator, NetworkValidator

logger = logging.getLogger(__name__)


@shared_task(name="scraping.tasks.update_adaptive_schedules")
def update_adaptive_schedules() -> dict[str, Any]:
    """Runs daily at 03:00 UTC and recalculates all source schedules."""
    from .adaptive_scheduler import AdaptiveScheduler

    scheduler = AdaptiveScheduler(lookback_runs=30)
    results = scheduler.update_all_sources()

    updated = len(results)
    logger.info("[AdaptiveScheduler] Updated %s source schedules", updated)

    tier_counts = Counter(r["new_tier"] for r in results)
    logger.info("[AdaptiveScheduler] Tier distribution: %s", dict(tier_counts))

    return {"updated": updated, "tiers": dict(tier_counts)}


def _sync_source_fail_fast_state(category: str, scraper) -> None:
    """Persist fail-fast network errors from scraper fetch() outcomes to sources."""
    from urllib.parse import urlparse

    from .models import ScrapingSource

    failures = getattr(scraper, "_network_failures", {}) or {}
    if not failures:
        return

    now = timezone.now()
    sources = ScrapingSource.objects.filter(category=category, is_active=True)

    for source in sources:
        source_url = (source.url or source.base_url or "").strip()
        domain = urlparse(source_url).netloc or ""
        if not domain:
            continue

        source_key = f"{domain}|{source.name}"
        error_type = failures.get(source_key) or failures.get(domain)
        if not error_type:
            continue

        source.last_error = error_type
        source.last_failed_at = now
        # Mark source inactive after 3 consecutive failures
        source.consecutive_failures = (source.consecutive_failures or 0) + 1
        if source.consecutive_failures >= 3:
            source.is_active = False
            logger.warning("Source %s marked inactive after 3 failures", source.name)

        source.save(
            update_fields=[
                "last_error",
                "last_failed_at",
                "consecutive_failures",
                "is_active",
            ]
        )
        continue  # Skip to next source


def push_scraping_progress(task_uuid: str, **kwargs):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"scraping_{task_uuid}",
        {
            "type": "status_update",
            "status": kwargs.get("status", "running"),
            "progress": int(kwargs.get("progress", 0)),
            "total": int(kwargs.get("total", 0)),
            "items_scraped": int(kwargs.get("items_scraped", 0)),
            "items_failed": int(kwargs.get("items_failed", 0)),
            "current_source": kwargs.get("current_source", ""),
            "message": kwargs.get("message", ""),
            "timestamp": timezone.now().isoformat(),
        },
    )


def _push_source_failed(source_name: str, reason: str):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        "scraping_status",
        {
            "type": "source_failed",
            "source": source_name,
            "reason": reason,
        },
    )


def _mark_source_failed_with_fallback(source, reason: str):
    now = timezone.now()
    source.is_active = False
    source.last_error = reason
    source.last_error_at = now
    source.last_failed_at = now
    source.save(
        update_fields=[
            "is_active",
            "last_error",
            "last_error_at",
            "last_failed_at",
        ]
    )
    _push_source_failed(source.name, reason)

    fallback_url = (source.fallback_url or "").strip()
    if not fallback_url:
        return

    try:
        network = NetworkValidator(fallback_url).run()
        if network.get("overall") != "RED":
            source.is_active = True
            source.last_error = ""
            source.save(update_fields=["is_active", "last_error"])
    except Exception as fallback_exc:
        _push_source_failed(source.name, type(fallback_exc).__name__)


@shared_task(
    bind=True,
    name="scraping.tasks.validate_source_async",
    queue=SCRAPING_CELERY_QUEUE,
)
def validate_source_async(self, source_id: str) -> dict[str, Any]:
    """Validate a source URL asynchronously without blocking admin saves."""
    from .models import ScrapingSource

    source = ScrapingSource.objects.filter(id=source_id).first()
    if source is None:
        return {"status": "error", "message": "Source not found"}

    def _validate_url(target_url: str):
        net = NetworkValidator(target_url).run()
        cnt = None
        if net.get("overall") != "RED":
            cnt = ContentValidator(target_url, source.category).run()
        return net, cnt

    source_url = (source.url or source.base_url or "").strip()
    last_exception: Exception | None = None
    tried_fallback = False

    try:
        network, content = _validate_url(source_url)
    except Exception as exc:
        last_exception = exc
        now = timezone.now()
        source.is_active = False
        source.last_error = str(exc)
        source.last_error_at = now
        source.last_failed_at = now
        source.validation_status = "RED"
        source.validation_detail = {
            "network": None,
            "content": None,
            "checked_at": now.isoformat(),
            "task_id": self.request.id,
            "exception": str(exc),
        }
        source.last_validated_at = now
        source.save(
            update_fields=[
                "is_active",
                "last_error",
                "last_error_at",
                "last_failed_at",
                "validation_status",
                "validation_detail",
                "last_validated_at",
            ]
        )
        _push_source_failed(source.name, type(exc).__name__)

        fallback_url = (source.fallback_url or "").strip()
        if fallback_url and fallback_url != source_url:
            tried_fallback = True
            try:
                network, content = _validate_url(fallback_url)
            except Exception as fallback_exc:
                _push_source_failed(source.name, type(fallback_exc).__name__)
                return {
                    "status": "error",
                    "source_id": source_id,
                    "message": str(fallback_exc),
                    "used_fallback": True,
                }
        else:
            return {
                "status": "error",
                "source_id": source_id,
                "message": str(exc),
                "used_fallback": False,
            }

    if (
        network.get("overall") == "RED"
        or content
        and content.get("verdict") == "IRRELEVANT"
    ):
        status = "RED"
    elif network.get("overall") == "YELLOW" or (
        content and content.get("verdict") == "UNCERTAIN"
    ):
        status = "YELLOW"
    elif content and content.get("verdict") == "RELEVANT":
        status = "GREEN"
    else:
        status = "RED"

    checked_at = timezone.now()
    source.validation_status = status
    if last_exception is None:
        source.last_error = ""
    if status == "RED":
        source.is_active = False
        source.last_error = source.last_error or "Validation failed"
        source.last_error_at = checked_at
        source.last_failed_at = checked_at
    else:
        source.is_active = True
    source.validation_detail = {
        "network": network,
        "content": content,
        "checked_at": checked_at.isoformat(),
        "task_id": self.request.id,
        "used_fallback": tried_fallback,
    }
    source.last_validated_at = checked_at
    source.save(
        update_fields=[
            "is_active",
            "validation_status",
            "validation_detail",
            "last_validated_at",
            "last_error",
            "last_error_at",
            "last_failed_at",
        ]
    )

    return {
        "status": "success",
        "source_id": source_id,
        "validation_status": status,
        "used_fallback": tried_fallback,
    }


@shared_task(
    bind=True,
    name="scraping.tasks.run_scraper_task",
    queue=SCRAPING_CELERY_QUEUE,
)
def run_scraper_task(
    self,
    category: str | None = None,
    run_id: str | None = None,
    allow_run_recreate: bool = False,
    user_id: int | None = None,
    source_id: str | None = None,
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
    from .models import ScrapingRun, ScrapingSource

    started_at = time.monotonic()
    category_tier = str(CATEGORY_META.get(category, {}).get("tier", 4))

    # Resolve or create the ScrapingRun record
    triggered_by = None
    if user_id:
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        triggered_by = user_model.objects.filter(pk=user_id).first()

    if source_id:
        from .scrapers.custom_scraper import CustomDomainScraper

        source = ScrapingSource.objects.filter(id=source_id, is_active=True).first()
        if source is None:
            raise ValueError(f"Active source {source_id} not found")

        category = category or source.category

        if run_id:
            run = ScrapingRun.objects.filter(id=run_id).first()
            if run is None and allow_run_recreate:
                run = ScrapingRun.objects.create(
                    category=category,
                    status="running",
                    triggered_by=triggered_by,
                    source=source,
                )
            elif run is None:
                raise ValueError(f"ScrapingRun {run_id} not found")
        else:
            run = ScrapingRun.objects.create(
                category=category,
                status="running",
                triggered_by=triggered_by,
                source=source,
            )

        run.task_id = self.request.id
        run.status = "running"
        run.save(update_fields=["task_id", "status"])

        scraper = CustomDomainScraper(source)
        results = scraper.scrape()
        items_created = len(results)
        items_failed = int(getattr(scraper, "items_failed", 0) or 0)

        run.items_found = items_created + items_failed
        run.items_created = items_created
        run.items_skipped = items_failed
        run.errors = "" if items_failed == 0 else f"{items_failed} items failed to save"
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "items_found",
                "items_created",
                "items_skipped",
                "errors",
                "status",
                "completed_at",
            ]
        )

        source.last_scraped = timezone.now()
        source.last_run_status = "success" if items_failed == 0 else "partial"
        source.last_run_items_created = items_created
        source.last_run_error = run.errors
        source.save(
            update_fields=[
                "last_scraped",
                "last_run_status",
                "last_run_items_created",
                "last_run_error",
            ]
        )

        return {
            "status": "success",
            "run_id": str(run.pk),
            "source_id": str(source.id),
            "items_found": run.items_found,
            "items_created": run.items_created,
            "items_skipped": run.items_skipped,
            "results": results,
            "duration": run.duration,
        }

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

    active_sources = list(
        ScrapingSource.objects.filter(category=category, is_active=True).order_by(
            "name"
        )
    )
    total_sources = len(active_sources)
    push_scraping_progress(
        str(run.id),
        status="running",
        progress=0,
        total=total_sources,
        items_scraped=0,
        items_failed=0,
        message="Scraping task started",
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
        push_scraping_progress(
            str(run.id),
            status="failed",
            progress=0,
            total=total_sources,
            items_scraped=0,
            items_failed=1,
            message=run.errors,
        )
        return {"status": "error", "message": run.errors}

    try:
        scraper = get_scraper(category)
        result = scraper.run()
        _sync_source_fail_fast_state(category, scraper)

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

        failed_sources = 0
        if getattr(scraper, "_network_failures", None):
            failed_sources = len(
                {
                    key.split("|", 1)[0]
                    for key in scraper._network_failures.keys()
                    if key
                }
            )

        if total_sources:
            for index, source in enumerate(active_sources, start=1):
                source_error = ""
                source_url = (source.url or source.base_url or "").strip()
                if getattr(scraper, "_network_failures", None):
                    from urllib.parse import urlparse

                    domain = urlparse(source_url).netloc or ""
                    source_key = f"{domain}|{source.name}"
                    source_error = (
                        scraper._network_failures.get(source_key)
                        or scraper._network_failures.get(domain)
                        or ""
                    )

                push_scraping_progress(
                    str(run.id),
                    status="running",
                    progress=index,
                    total=total_sources,
                    current_source=source.name,
                    items_scraped=int(run.items_created or 0),
                    items_failed=failed_sources,
                    message=(
                        f"Skipped {source.name}: {source_error}" if source_error else ""
                    ),
                )

        push_scraping_progress(
            str(run.id),
            status="completed",
            progress=total_sources,
            total=total_sources,
            items_scraped=int(run.items_created or 0),
            items_failed=failed_sources,
            message="Scraping task completed",
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
        from .models import ScrapingSource

        run.status = "failed"
        run.errors = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "errors", "completed_at"])

        for source in ScrapingSource.objects.filter(category=category, is_active=True):
            _mark_source_failed_with_fallback(source, type(exc).__name__)

        record_dead_letter(
            category=category,
            source_name="all_sources",
            item={"url": "unknown", "title": f"run_id={run.id}"},
            error=str(exc),
            retry_count=DEAD_LETTER_INITIAL_RETRY_COUNT,
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
        push_scraping_progress(
            str(run.id),
            status="failed",
            progress=0,
            total=total_sources,
            items_scraped=int(run.items_created or 0),
            items_failed=1,
            message=str(exc),
        )
        raise  # Re-raise so Celery marks the task as FAILURE


@shared_task(
    bind=True,
    name="scraping.tasks.run_events_pipeline_task",
    queue=SCRAPING_CELERY_QUEUE,
)
def run_events_pipeline_task(self, run_id: str | None = None) -> dict[str, Any]:
    """Example integration entrypoint for the production-ready events pipeline."""
    from .models import ScrapingRun

    run = None
    if run_id:
        run = ScrapingRun.objects.filter(id=run_id).first()
    if run is None:
        run = ScrapingRun.objects.create(category="events", status="running")

    run.task_id = self.request.id
    run.status = "running"
    run.save(update_fields=["task_id", "status"])

    manager = EventScraperManager(run_id=str(run.id))
    started_at = time.monotonic()

    try:
        result = manager.run()

        run.items_found = int(result.get("created", 0)) + int(result.get("skipped", 0))
        run.items_created = int(result.get("created", 0))
        run.items_skipped = int(result.get("skipped", 0))
        run.errors = "\n".join(result.get("save_errors", []))
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "items_found",
                "items_created",
                "items_skipped",
                "errors",
                "status",
                "completed_at",
            ]
        )

        scrape_runs_total.labels(category="events", status="success").inc()
        scrape_duration_seconds.labels(category="events").observe(
            time.monotonic() - started_at
        )
        scrape_items_total.labels(category="events", outcome="created").inc(
            run.items_created
        )
        scrape_items_total.labels(category="events", outcome="skipped").inc(
            run.items_skipped
        )
        update_scrape_queue_lag_metrics(force=True)

        return {
            "status": "success",
            "run_id": str(run.id),
            "items_found": run.items_found,
            "items_created": run.items_created,
            "items_skipped": run.items_skipped,
            "errors": result.get("source_failures", {}),
        }
    except Exception as exc:
        run.status = "failed"
        run.errors = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "errors", "completed_at"])

        scrape_runs_total.labels(category="events", status="failed").inc()
        scrape_duration_seconds.labels(category="events").observe(
            time.monotonic() - started_at
        )
        update_scrape_queue_lag_metrics(force=True)
        raise
