"""
Celery tasks for the Web Scraping module.

Provides background execution of scrapers so the admin dashboard
returns immediately while scraping runs asynchronously.
"""

import logging
import time
import traceback
from collections import Counter
from datetime import datetime
from typing import Any

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from .constants import SCRAPING_CELERY_QUEUE
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
from .validators import ContentValidator, NetworkValidator

logger = logging.getLogger(__name__)

SUPPORTED_SCRAPER_CATEGORIES = (
    "events",
    "tools",
    "courses",
    "news",
    "opportunities",
    "corpus",
)
SUPPORTED_SCRAPER_CATEGORY_SET = set(SUPPORTED_SCRAPER_CATEGORIES)


def _category_display_label(category: str) -> str:
    meta = CATEGORY_META.get(category, {})
    return str(meta.get("label") or category.title())


def _create_scraping_notification(
    *,
    notification_type: str,
    message: str,
    category: str = "",
    run=None,
    source=None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort notification creation for scraping admin UI."""
    from .models import ScrapingNotification

    try:
        ScrapingNotification.objects.create(
            notification_type=notification_type,
            category=category or "",
            message=(message or "").strip()[:500],
            run=run,
            source=source,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning(
            "scraping_notification_create_failed",
            extra={
                "notification_type": notification_type,
                "category": category,
                "error": str(exc),
            },
        )


@shared_task(name="scraping.tasks.update_adaptive_schedules")
def update_adaptive_schedules() -> dict[str, Any]:
    """Runs daily at 03:00 UTC and recalculates all source schedules."""
    if getattr(settings, "SCRAPING_MANUAL_ONLY", False):
        logger.info("adaptive_scheduler_skipped_manual_only")
        return {"updated": 0, "tiers": {}, "skipped": True}

    from .adaptive_scheduler import AdaptiveScheduler

    scheduler = AdaptiveScheduler(lookback_runs=30)
    results = scheduler.update_all_sources()

    updated = len(results)
    logger.info("[AdaptiveScheduler] Updated %s source schedules", updated)

    tier_counts = Counter(r["new_tier"] for r in results)
    logger.info("[AdaptiveScheduler] Tier distribution: %s", dict(tier_counts))

    return {"updated": updated, "tiers": dict(tier_counts)}


def _sync_source_fail_fast_state(category: str, scraper, run_id: str = "") -> None:
    """Persist fail-fast network errors from scraper fetch() outcomes to sources."""
    from urllib.parse import urlparse

    from .models import ScrapingSource

    failures = getattr(scraper, "_network_failures", {}) or {}
    sources = ScrapingSource.objects.filter(category=category, is_active=True)

    for source in sources:
        if getattr(source, "is_admin_disabled", False):
            continue

        source_url = (source.url or source.base_url or "").strip()
        domain = urlparse(source_url).netloc or ""
        if not domain:
            continue

        source_key = f"{domain}|{source.name}"
        error_type = failures.get(source_key) or failures.get(domain)
        if error_type:
            previous_failures = int(getattr(source, "consecutive_failures", 0) or 0)
            _mark_source_failed_with_fallback(
                source,
                error=str(error_type),
                run_id=run_id,
            )
            reached_failure_threshold = (
                previous_failures
                < _source_failure_threshold()
                <= int(getattr(source, "consecutive_failures", 0) or 0)
            )
            if not reached_failure_threshold:
                continue

            category_label = _category_display_label(category)
            _create_scraping_notification(
                notification_type="source_failing",
                category=category,
                source=source,
                message=(
                    f'[{category_label}] Source "{source.name}" was disabled '
                    f"after {_source_failure_threshold()} consecutive failures."
                ),
                metadata={
                    "source_id": str(source.id),
                    "error_type": error_type,
                    "consecutive_failures": int(source.consecutive_failures or 0),
                },
            )
            continue

        _mark_source_success(source)


def _source_failure_threshold() -> int:
    return max(1, int(getattr(settings, "SCRAPING_SOURCE_FAILURE_THRESHOLD", 3) or 3))


def push_scraping_progress(
    task_uuid: str, payload: dict[str, Any] | None = None, **kwargs
):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    data: dict[str, Any] = {}
    if payload:
        data.update(payload)
    data.update(kwargs)

    progress_value = int(
        data.get("current", data.get("progress_current", data.get("progress", 0))) or 0
    )
    total_value = int(data.get("total", data.get("progress_total", 0)) or 0)
    current_step = str(data.get("step", data.get("current_step", "")) or "")
    current_message = str(
        data.get("message", data.get("current_message", data.get("current_step", "")))
        or ""
    )
    items_created = int(data.get("items_created", data.get("items_scraped", 0)) or 0)
    items_failed = int(data.get("items_failed", data.get("items_skipped", 0)) or 0)
    current_item = data.get("current_item", data.get("current_source", ""))
    percent_value = int((progress_value / total_value) * 100) if total_value > 0 else 0

    try:
        async_to_sync(channel_layer.group_send)(
            f"scraping_{task_uuid}",
            {
                "type": "scraping_event",
                "event_type": str(data.get("event_type", "progress") or "progress"),
                "run_id": str(task_uuid),
                "task_uuid": str(task_uuid),
                "status": data.get("status", "running"),
                "step": current_step,
                "current": progress_value,
                "total": total_value,
                "percent": percent_value,
                "progress": progress_value,
                "total": total_value,
                "progress_current": progress_value,
                "progress_total": total_value,
                "items_created": items_created,
                "items_scraped": items_created,
                "items_failed": items_failed,
                "current_source": data.get("current_source", ""),
                "current_item": current_item,
                "current_step": current_step,
                "current_message": current_message,
                "message": current_message,
                "timestamp": timezone.now().isoformat(),
            },
        )
    except Exception as exc:
        logger.debug("scraping_progress_ws_emit_failed error=%s", exc)


def _push_source_event(run_id: str, event_type: str, data: dict[str, Any]):
    """Push source-level events to the per-run websocket group."""
    if not run_id:
        return

    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(
            f"scraping_{run_id}",
            {
                "type": "scraping_event",
                "event_type": event_type,
                "run_id": str(run_id),
                "task_uuid": str(run_id),
                **(data or {}),
            },
        )
    except Exception as exc:
        logger.warning("WebSocket push failed: %s", exc)


def _push_source_failed(run_id: str, source_url: str, error: str):
    _push_source_event(
        run_id,
        "source_failed",
        {
            "source_url": source_url,
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def _mark_source_failed_with_fallback(source, error: str = "", run_id: str = ""):
    """Apply graduated failure policy before disabling source."""
    now = timezone.now()
    source.consecutive_failures = (
        int(getattr(source, "consecutive_failures", 0) or 0) + 1
    )
    source.last_failure_reason = str(error or "")[:200]
    source.last_failure_at = now
    source.last_error = str(error or "")[:255]
    source.last_error_at = now
    source.last_failed_at = now
    source.fail_count = int(getattr(source, "fail_count", 0) or 0) + 1

    failure_threshold = _source_failure_threshold()
    update_fields = [
        "consecutive_failures",
        "last_failure_reason",
        "last_failure_at",
        "last_error",
        "last_error_at",
        "last_failed_at",
        "fail_count",
    ]

    if int(source.consecutive_failures or 0) >= failure_threshold:
        source.is_active = False
        source.quarantine_reason = (
            f"Auto-quarantined after {source.consecutive_failures} consecutive failures. "
            f"Last error: {str(error or '')[:100]}"
        )
        update_fields.extend(["is_active", "quarantine_reason"])
        logger.warning(
            "Source quarantined after %s failures: %s",
            failure_threshold,
            source.url or source.base_url or source.name,
        )

    source.save(update_fields=list(dict.fromkeys(update_fields)))
    _push_source_failed(
        run_id, source.url or source.base_url or source.name, str(error or "")
    )


def _mark_source_success(source):
    """Reset source failure counters after a successful run."""
    now = timezone.now()
    source.consecutive_failures = 0
    source.last_failure_reason = ""
    source.last_error = ""
    source.last_error_at = None
    source.quarantine_reason = ""
    source.last_scraped = now

    update_fields = [
        "consecutive_failures",
        "last_failure_reason",
        "last_error",
        "last_error_at",
        "quarantine_reason",
        "last_scraped",
    ]

    if hasattr(source, "last_success_at"):
        source.last_success_at = now
        update_fields.append("last_success_at")

    source.save(update_fields=update_fields)


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
                "last_error",
                "last_error_at",
                "last_failed_at",
                "validation_status",
                "validation_detail",
                "last_validated_at",
            ]
        )
        _mark_source_failed_with_fallback(
            source,
            error=str(exc),
            run_id=str(self.request.id or ""),
        )
        _push_source_failed(
            str(self.request.id or ""),
            source.url or source.base_url or source.name,
            type(exc).__name__,
        )

        fallback_url = (source.fallback_url or "").strip()
        if fallback_url and fallback_url != source_url:
            tried_fallback = True
            try:
                network, content = _validate_url(fallback_url)
            except Exception as fallback_exc:
                _mark_source_failed_with_fallback(
                    source,
                    error=str(fallback_exc),
                    run_id=str(self.request.id or ""),
                )
                _push_source_failed(
                    str(self.request.id or ""),
                    source.url or source.base_url or source.name,
                    type(fallback_exc).__name__,
                )
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
        source.last_error = source.last_error or "Validation failed"
        source.last_error_at = checked_at
        source.last_failed_at = checked_at
        _mark_source_failed_with_fallback(
            source,
            error=str(source.last_error or "Validation failed"),
            run_id=str(self.request.id or ""),
        )
    else:
        if not getattr(source, "is_admin_disabled", False):
            source.is_active = True
        _mark_source_success(source)
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
        category: One of: events, tools, courses, news, opportunities, corpus.
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

    category = str(category).strip().lower() if category is not None else None
    started_at = time.monotonic()

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

        category = (
            (category or str(source.category or "").strip().lower()).strip().lower()
        )
        if category not in SUPPORTED_SCRAPER_CATEGORY_SET:
            raise ValueError(
                "Unsupported category: "
                f"{category}. Supported categories: "
                f"{', '.join(SUPPORTED_SCRAPER_CATEGORIES)}"
            )

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
        run.progress_current = 0
        run.progress_total = 1
        run.current_step = "🔍 Searching: custom source"
        run.current_message = run.current_step
        run.current_source = source.name
        run.current_item = source.name
        run.items_failed = 0
        run.save(
            update_fields=[
                "task_id",
                "status",
                "progress_current",
                "progress_total",
                "current_step",
                "current_message",
                "current_source",
                "current_item",
                "items_failed",
            ]
        )

        push_scraping_progress(
            str(run.id),
            status="running",
            step="discovery",
            progress_current=0,
            progress_total=1,
            items_scraped=0,
            items_failed=0,
            current_source=source.name,
            current_item=source.name,
            current_step=run.current_step,
            message=run.current_step,
        )

        scraper = CustomDomainScraper(source)
        try:
            if hasattr(scraper, "bind_progress_run"):
                scraper.bind_progress_run(run)
            results = scraper.scrape()
            items_created = len(results)
            items_failed = int(getattr(scraper, "items_failed", 0) or 0)

            run.items_found = items_created + items_failed
            run.items_created = items_created
            run.items_skipped = items_failed
            run.items_failed = items_failed
            run.errors = (
                "" if items_failed == 0 else f"{items_failed} items failed to save"
            )
            run.status = "completed"
            run.progress_current = 1
            run.progress_total = 1
            run.current_step = "Completed"
            run.current_message = "Scraping task completed"
            run.current_source = source.name
            run.current_item = ""
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "items_found",
                    "items_created",
                    "items_skipped",
                    "items_failed",
                    "errors",
                    "status",
                    "progress_current",
                    "progress_total",
                    "current_step",
                    "current_message",
                    "current_source",
                    "current_item",
                    "completed_at",
                ]
            )

            push_scraping_progress(
                str(run.id),
                status="completed",
                step="saving",
                progress_current=1,
                progress_total=1,
                items_scraped=int(run.items_created or 0),
                items_failed=int(run.items_failed or run.items_skipped or 0),
                current_source=source.name,
                current_item="",
                current_step="Completed",
                message="Scraping task completed",
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

            category_label = _category_display_label(category)
            _create_scraping_notification(
                notification_type="run_complete",
                category=category,
                run=run,
                source=source,
                message=(
                    f"[{category_label}] Run #{str(run.id)[:8]} completed "
                    f"({int(run.items_created or 0)} created, {int(run.items_skipped or 0)} skipped)."
                ),
                metadata={
                    "run_id": str(run.id),
                    "source_id": str(source.id),
                    "items_created": int(run.items_created or 0),
                    "items_skipped": int(run.items_skipped or 0),
                },
            )

            return {
                "status": "success",
                "run_id": str(run.pk),
                "source_id": str(source.id),
                "items_found": run.items_found,
                "items_created": run.items_created,
                "items_skipped": run.items_skipped,
                "items_failed": run.items_failed,
                "results": results,
                "duration": run.duration,
            }
        except Exception as exc:
            run.status = "failed"
            run.errors = str(exc)
            run.current_step = str(exc)[:100]
            run.current_message = str(exc)[:255]
            run.current_item = source.name
            run.items_failed = int(run.items_skipped or 0) + 1
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "errors",
                    "current_step",
                    "current_message",
                    "current_item",
                    "items_failed",
                    "completed_at",
                ]
            )

            category_label = _category_display_label(category)
            _create_scraping_notification(
                notification_type="run_failed",
                category=category,
                run=run,
                source=source,
                message=f"[{category_label}] Run #{str(run.id)[:8]} failed: {type(exc).__name__}.",
                metadata={
                    "run_id": str(run.id),
                    "source_id": str(source.id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise

    if not category:
        raise ValueError(
            "Category is required. Supported categories: "
            f"{', '.join(SUPPORTED_SCRAPER_CATEGORIES)}"
        )
    if category not in SUPPORTED_SCRAPER_CATEGORY_SET:
        raise ValueError(
            "Unsupported category: "
            f"{category}. Supported categories: "
            f"{', '.join(SUPPORTED_SCRAPER_CATEGORIES)}"
        )

    category_tier = str(CATEGORY_META.get(category, {}).get("tier", 4))

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
    run.progress_current = 0
    run.progress_total = 0
    run.current_step = "Scraping task started"
    run.current_message = run.current_step
    run.current_source = ""
    run.current_item = ""
    run.items_failed = 0
    run.save(
        update_fields=[
            "task_id",
            "status",
            "progress_current",
            "progress_total",
            "current_step",
            "current_message",
            "current_source",
            "current_item",
            "items_failed",
        ]
    )

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
        step="discovery",
        progress_current=0,
        progress_total=total_sources,
        items_scraped=0,
        items_failed=0,
        current_item="",
        current_step="Scraping task started",
        message="Scraping task started",
    )

    if category not in SUPPORTED_SCRAPER_CATEGORY_SET:
        run.status = "failed"
        run.errors = f"Unknown category: {category}"
        run.current_step = run.errors
        run.current_message = run.errors[:255]
        run.progress_current = 0
        run.progress_total = total_sources
        run.current_item = ""
        run.items_failed = 1
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_step",
                "current_message",
                "progress_current",
                "progress_total",
                "current_item",
                "items_failed",
                "completed_at",
            ]
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
        update_scrape_queue_lag_metrics(force=True)
        push_scraping_progress(
            str(run.id),
            status="failed",
            step="discovery",
            progress_current=0,
            progress_total=total_sources,
            items_scraped=0,
            items_failed=1,
            current_item="",
            current_step=run.errors,
            message=run.errors,
        )
        category_label = _category_display_label(category)
        _create_scraping_notification(
            notification_type="run_failed",
            category=category,
            run=run,
            message=f"[{category_label}] Run #{str(run.id)[:8]} failed: unsupported category.",
            metadata={"run_id": str(run.id), "error": run.errors},
        )
        return {"status": "error", "message": run.errors}

    try:
        scraper = get_scraper(category)
        if hasattr(scraper, "bind_progress_run"):
            scraper.bind_progress_run(run)
        result = scraper.run()
        _sync_source_fail_fast_state(category, scraper, run_id=str(run.id))

        run.items_found = result.get("items_found", 0)
        run.items_created = result.get("items_created", 0)
        run.items_updated = result.get("items_updated", 0)
        run.items_skipped = result.get("items_skipped", 0)
        run.items_failed = int(run.items_skipped or 0)
        result_errors = result.get("errors", [])
        if not isinstance(result_errors, list):
            result_errors = [str(result_errors)] if result_errors else []
        run.errors = "\n".join(str(err) for err in result_errors if err)
        has_run_errors = bool(run.errors.strip())
        has_persisted_items = bool(
            int(run.items_found or 0)
            or int(run.items_created or 0)
            or int(run.items_updated or 0)
        )
        run_failed = has_run_errors and not has_persisted_items
        if run_failed and run.items_failed == 0:
            run.items_failed = 1
        run.progress_total = int(run.progress_total or total_sources or 1)
        run.progress_current = int(run.progress_current or run.progress_total)
        if run.progress_current < run.progress_total:
            run.progress_current = run.progress_total
        run.current_step = "Failed" if run_failed else "Completed"
        run.current_message = (
            "Scraping task failed" if run_failed else "Scraping task completed"
        )
        run.current_source = ""
        run.current_item = ""
        run.status = "failed" if run_failed else "completed"
        run.completed_at = timezone.now()
        run.save()

        scrape_runs_total.labels(
            category=category,
            status="failed" if run_failed else "success",
        ).inc()
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
        if run.items_updated:
            scrape_items_total.labels(category=category, outcome="updated").inc(
                run.items_updated
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
        if run_failed and not run.items_skipped:
            scrape_source_items_total.labels(
                category=category,
                source_name="all_sources",
                outcome="skipped_error",
            ).inc(1)
        update_source_health_metrics(category=category)
        update_scrape_queue_lag_metrics(force=True)

        category_label = _category_display_label(category)
        if run_failed:
            logger.error(
                "scrape_task_failed",
                extra={
                    "category": category,
                    "run_id": str(run.id),
                    "error": run.errors,
                    "error_type": "ScraperReportedError",
                },
            )
            push_scraping_progress(
                str(run.id),
                status="failed",
                step="saving",
                progress_current=int(run.progress_current or 0),
                progress_total=int(run.progress_total or 0),
                items_scraped=int(run.items_created or 0),
                items_failed=int(run.items_failed or run.items_skipped or 0),
                current_source=run.current_source,
                current_item=run.current_item,
                current_step=run.current_step,
                message=run.errors or "Scraping task failed",
            )
            _create_scraping_notification(
                notification_type="run_failed",
                category=category,
                run=run,
                message=(
                    f"[{category_label}] Run #{str(run.id)[:8]} failed: "
                    f"{(run.errors or 'scraper error')[:160]}."
                ),
                metadata={
                    "run_id": str(run.id),
                    "items_found": int(run.items_found or 0),
                    "items_created": int(run.items_created or 0),
                    "items_updated": int(run.items_updated or 0),
                    "items_skipped": int(run.items_skipped or 0),
                    "error": run.errors,
                },
            )
        else:
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

            push_scraping_progress(
                str(run.id),
                status="completed",
                step="saving",
                progress_current=int(run.progress_current or 0),
                progress_total=int(run.progress_total or 0),
                items_scraped=int(run.items_created or 0),
                items_failed=int(run.items_failed or run.items_skipped or 0),
                current_source=run.current_source,
                current_item=run.current_item,
                current_step=run.current_step,
                message="Scraping task completed",
            )

            _create_scraping_notification(
                notification_type="run_complete",
                category=category,
                run=run,
                message=(
                    f"[{category_label}] Run #{str(run.id)[:8]} completed "
                    f"({int(run.items_created or 0)} created, {int(run.items_skipped or 0)} skipped)."
                ),
                metadata={
                    "run_id": str(run.id),
                    "items_found": int(run.items_found or 0),
                    "items_created": int(run.items_created or 0),
                    "items_updated": int(run.items_updated or 0),
                    "items_skipped": int(run.items_skipped or 0),
                },
            )

        return {
            "status": "error" if run_failed else "success",
            "run_id": str(run.pk),
            "items_found": run.items_found,
            "items_created": run.items_created,
            "items_updated": run.items_updated,
            "items_skipped": run.items_skipped,
            "items_failed": run.items_failed,
            "errors": result_errors,
            "results": result.get("results", []),
            "duration": run.duration,
        }

    except Exception as exc:
        logger.error(
            "Global exception in scraping run %s: %s",
            str(run.id),
            exc,
            exc_info=True,
        )
        run.status = "failed"
        run.errors = str(exc)
        run.current_step = str(exc)[:100]
        run.current_message = str(exc)[:255]
        run.current_item = run.current_source
        run.items_failed = int(run.items_skipped or 0) + 1
        run.progress_total = int(run.progress_total or total_sources)
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_step",
                "current_message",
                "current_item",
                "items_failed",
                "progress_total",
                "completed_at",
            ]
        )
        record_dead_letter(
            category=category,
            url="global_run_exception",
            reason=str(exc)[:200],
            data={
                "run_id": str(run.id),
                "traceback": traceback.format_exc(),
            },
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
            step="saving",
            progress_current=int(run.progress_current or 0),
            progress_total=int(run.progress_total or 0),
            items_scraped=int(run.items_created or 0),
            items_failed=int(run.items_failed or run.items_skipped or 0),
            current_source=run.current_source,
            current_item=run.current_item,
            current_step=run.current_step,
            message=str(exc),
        )

        category_label = _category_display_label(category)
        _create_scraping_notification(
            notification_type="run_failed",
            category=category,
            run=run,
            message=f"[{category_label}] Run #{str(run.id)[:8]} failed: {type(exc).__name__}.",
            metadata={
                "run_id": str(run.id),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise  # Re-raise so Celery marks the task as FAILURE


@shared_task(
    bind=True,
    name="scraping.tasks.run_events_pipeline_task",
    queue=SCRAPING_CELERY_QUEUE,
)
def run_events_pipeline_task(self, run_id: str | None = None) -> dict[str, Any]:
    """Run the events category using the active scraper registry."""
    from .models import ScrapingRun

    run = None
    if run_id:
        run = ScrapingRun.objects.filter(id=run_id).first()
    if run is None:
        run = ScrapingRun.objects.create(category="events", status="running")

    run.task_id = self.request.id
    run.status = "running"
    run.save(update_fields=["task_id", "status"])

    scraper = get_scraper("events")
    started_at = time.monotonic()

    try:
        summary = scraper.run()

        run.items_found = int(summary.get("items_found", 0))
        run.items_created = int(summary.get("items_created", 0))
        run.items_skipped = int(summary.get("items_skipped", 0))
        run.items_failed = int(run.items_skipped or 0)
        run.errors = "\n".join(summary.get("errors", []))
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "items_found",
                "items_created",
                "items_skipped",
                "items_failed",
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
            "items_failed": run.items_failed,
            "errors": summary.get("errors", []),
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
