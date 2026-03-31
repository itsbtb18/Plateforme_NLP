"""
Views for the Web Scraping module.

Supports both synchronous (fallback) and asynchronous (Celery) execution.
"""

import functools
import json
import logging
import os
import threading
import uuid
from collections import defaultdict
from ipaddress import ip_address, ip_network

from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db.models import Count, Max, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST
from events.models import Event
from institutions.models import Institution
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from feed.models import Post
from resources.models import Course, NLPTool

from scraping.intelligence import detect_trends
from scraping.scrapers.custom_scraper import CustomDomainScraper
from scraping.validators import ContentValidator, NetworkValidator

from .constants import SKIP_DEDUP_SIMILARITY, SOURCE_TIER_TOKEN_MAP
from .metrics import update_scrape_queue_lag_metrics, update_source_health_metrics
from .models import ScrapedItemMeta, ScrapingRun, ScrapingSource, ScrapingSourceHealth
from .scrapers import CATEGORY_META, get_all_categories, get_scraper
from .scraping_settings import scraping_settings as SS
from .tasks import run_scraper_task


def rate_limit(max_calls: int, period_seconds: int, scope: str = "global"):
    """Create a per-user/per-path rate-limit decorator for JSON views.

    Args:
        max_calls: Maximum number of requests allowed in the period.
        period_seconds: Rolling window size in seconds.
        scope: Prefix namespace used when building the rate-limit cache key.

    Returns:
        callable: Decorator that enforces limits and returns HTTP 429 on excess.
    """

    def decorator(view_func):
        """Wrap a view with token-bucket style request limiting."""

        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            """Execute view when within quota, otherwise return a 429 response."""
            if request.user.is_authenticated and request.user.id is not None:
                rate_key = f"{scope}:{request.user.id}:{request.path}"
            else:
                rate_key = f"{scope}:anon:{_client_ip(request)}"

            if not _enforce_rate_limit(rate_key, max_calls, period_seconds):
                return JsonResponse(
                    {
                        "error": "rate_limit_exceeded",
                        "message": (
                            f"Max {max_calls} requests per {period_seconds}s exceeded."
                        ),
                        "retry_after": period_seconds,
                    },
                    status=429,
                    headers={"Retry-After": str(period_seconds)},
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


logger = logging.getLogger(__name__)

RATE_LIMIT_MAP = {
    "polling": SS.VIEW_RATE_DEFAULT,
    "action": SS.VIEW_RATE_TRIGGER,
    "analytics": SS.VIEW_RATE_STANDARD,
    "metrics": SS.VIEW_RATE_METRICS,
}
RATE_LIMIT_WINDOW_SECONDS = SS.VIEW_RATE_WINDOW_SECONDS


def _ensure_default_scraping_sources() -> None:
    """Seed per-category default sources when a category has no active sources."""
    for category, meta in CATEGORY_META.items():
        if ScrapingSource.objects.filter(category=category, is_active=True).exists():
            continue

        defaults = list(meta.get("sources") or [])
        for source_name in defaults:
            ScrapingSource.objects.create(
                name=source_name,
                category=category,
                base_url="",
                description="Default source",
                is_active=True,
                scrape_config={"is_default": True},
                use_rss=False,
                use_llm_extraction=True,
            )


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _log_scraping_action(request):
    user_repr = (
        getattr(request.user, "email", None)
        or getattr(request.user, "username", None)
        or "anonymous"
    )
    logger.info(
        "scraping_action user=%s endpoint=%s method=%s timestamp=%s ip=%s",
        user_repr,
        request.path,
        request.method,
        timezone.now().isoformat(),
        _client_ip(request),
    )


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """
    Thread-safe and multi-process-safe rate limiter.
    Uses atomic Redis INCR with TTL to count requests
    across all workers within a sliding window.
    Returns True if request is allowed, False if limit exceeded.
    """
    import logging

    from django.core.cache import cache

    logger = logging.getLogger(__name__)

    cache_key = f"rate_limit:{key}"

    try:
        # Try to increment - atomic operation
        current = cache.get(cache_key)

        if current is None:
            # First request in this window
            cache.set(cache_key, 1, timeout=window_seconds)
            return True

        if int(current) >= limit:
            logger.info(
                "rate_limit_exceeded",
                extra={
                    "key": key,
                    "current": current,
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
            )
            return False

        # Increment without resetting TTL
        try:
            cache.incr(cache_key)
        except ValueError:
            # Key expired between get and incr - reset
            cache.set(cache_key, 1, timeout=window_seconds)

        return True

    except Exception as exc:
        # Fail open - if cache is unavailable, allow request
        logger.warning(
            "rate_limit_cache_error",
            extra={"error": str(exc), "key": key},
        )
        return True


def _require_staff(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    return None


def _require_json_content_type(request):
    content_type = request.META.get("CONTENT_TYPE", "")
    if not content_type.lower().startswith("application/json"):
        return JsonResponse(
            {"error": "Content-Type must be application/json"},
            status=415,
        )
    return None


def is_admin(user):
    """Check if user is an admin."""
    return user.is_staff or user.is_superuser


_TIER_LABELS = {
    1: "Algerian",
    2: "Arabic/MENA",
    3: "African",
    4: "Global",
}

_STATE_BADGE = {
    "closed": "green",
    "half_open": "amber",
    "open": "red",
}


def _infer_source_tier(
    source_name: str, source_url: str, source_category: str = ""
) -> int:
    config_tier = CATEGORY_META.get(source_category, {}).get("tier")
    if isinstance(config_tier, int) and config_tier in _TIER_LABELS:
        return config_tier

    blob = f"{source_name or ''} {source_url or ''}".lower()
    for inferred_tier in (1, 2, 3):
        tokens = SOURCE_TIER_TOKEN_MAP.get(inferred_tier, ())
        if any(token in blob for token in tokens):
            return inferred_tier
    return 4


def _model_for_category(category: str):
    if category == "events":
        return Event
    if category == "news":
        return Post
    if category == "courses":
        return Course
    if category == "tools":
        return NLPTool
    if category == "institutions":
        return Institution
    return None


def _resolve_source_name_from_meta(meta: ScrapedItemMeta) -> str:
    if meta.source_name:
        return meta.source_name
    return meta.item_title[:50] if meta.item_title else "Unknown"


def _match_confidence_for_reason(meta: ScrapedItemMeta) -> float:
    if meta.match_score is not None:
        return round(meta.match_score * 100, 1)
    fallback_map = {
        "dedup_url": 100.0,
        "dedup_doi": 100.0,
        "dedup_arxiv": 100.0,
        "dedup_ror": 100.0,
        "dedup_name": 100.0,
        "dedup_similarity": float(SS.FALLBACK_DEDUP_CONFIDENCE),
        "dedup_embedding": 70.0,
    }
    return fallback_map.get(meta.skip_reason, float(SS.FALLBACK_DEDUP_CONFIDENCE))


def _build_skip_reason_payload(category: str | None = None):
    base_qs = ScrapedItemMeta.objects.filter(was_skipped=True)
    if category:
        base_qs = base_qs.filter(category=category)

    skip_choices = [choice[0] for choice in ScrapedItemMeta.SKIP_REASON_CHOICES]
    per_category = defaultdict(lambda: defaultdict(int))
    per_source = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for meta in base_qs.only("category", "skip_reason", "item_id"):
        reason = (meta.skip_reason or "").strip()
        if reason not in skip_choices:
            reason = SKIP_DEDUP_SIMILARITY
        cat = meta.category
        source_name = _resolve_source_name_from_meta(meta)
        per_category[cat][reason] += 1
        per_source[cat][source_name][reason] += 1

    category_out = {
        cat: {
            reason: counts.get(reason, 0)
            for reason in skip_choices
            if counts.get(reason, 0)
        }
        for cat, counts in per_category.items()
    }

    source_out = {}
    for cat, source_counts in per_source.items():
        source_out[cat] = {
            source: {
                reason: reasons.get(reason, 0)
                for reason in skip_choices
                if reasons.get(reason, 0)
            }
            for source, reasons in source_counts.items()
        }

    return {
        "per_category": category_out,
        "per_source": source_out,
    }


def _build_source_health_rows(category: str | None = None):
    qs = ScrapingSource.objects.filter(is_active=True)
    if category:
        qs = qs.filter(category=category)

    rows = []
    for source in qs.order_by("category", "name"):
        health = ScrapingSourceHealth.objects.filter(
            category=source.category,
            source_name=source.name,
        ).first()
        tier = _infer_source_tier(source.name, source.base_url, source.category)

        avg_items_per_run = 0.0
        successes = int(getattr(health, "total_successes", 0) or 0)
        if successes > 0:
            saved_count = ScrapedItemMeta.objects.filter(
                category=source.category,
                was_skipped=False,
                item_id__isnull=False,
            ).count()
            avg_items_per_run = round(saved_count / successes, 2)
        elif source.last_run_items_created:
            avg_items_per_run = float(source.last_run_items_created)

        rows.append(
            {
                "id": str(source.id),
                "category": source.category,
                "source_name": source.name,
                "source_url": source.base_url,
                "tier": tier,
                "tier_label": _TIER_LABELS[tier],
                "circuit_state": getattr(health, "circuit_state", "closed"),
                "circuit_badge": _STATE_BADGE.get(
                    getattr(health, "circuit_state", "closed"),
                    "amber",
                ),
                "last_success_at": (
                    health.last_success_at.isoformat()
                    if health and health.last_success_at
                    else None
                ),
                "consecutive_failures": int(
                    getattr(health, "consecutive_failures", 0) or 0
                ),
                "average_items_per_run": avg_items_per_run,
            }
        )

    return rows


def _build_recent_runs_rows(category: str, limit: int = SS.VIEW_RECENT_RUNS_LIMIT):
    runs = ScrapingRun.objects.filter(category=category).order_by("-started_at")[:limit]
    output = []
    for run in runs:
        output.append(
            {
                "run_id": str(run.id),
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "duration_seconds": run.duration,
                "items_saved": int(run.items_created or 0),
                "items_skipped": int(run.items_skipped or 0),
                "items_found": int(run.items_found or 0),
                "error_message": run.errors if run.status == "failed" else "",
                "rerun_url": reverse("scraping:rerun_scraping_run", args=[run.id]),
            }
        )
    return output


def _build_duplicate_preview(category: str, run_id: str | None = None):
    qs = ScrapedItemMeta.objects.filter(category=category, was_skipped=True).exclude(
        skip_reason__isnull=True
    )

    if run_id:
        run = ScrapingRun.objects.filter(pk=run_id, category=category).first()
        if run is None:
            return None, "Run not found"
        started = run.started_at
        finished = run.completed_at or timezone.now()
        qs = qs.filter(created_at__gte=started, created_at__lte=finished)

    model_cls = _model_for_category(category)
    rows = []
    for meta in qs.order_by("-created_at")[:250]:
        matched_admin_url = ""
        matched_label = ""
        if model_cls is not None and meta.item_id:
            try:
                matched = model_cls.objects.filter(pk=meta.item_id).first()
                if matched is not None:
                    app_label = matched._meta.app_label
                    model_name = matched._meta.model_name
                    matched_admin_url = reverse(
                        f"admin:{app_label}_{model_name}_change",
                        args=[matched.pk],
                    )
                    matched_label = str(matched)
            except Exception:
                matched_admin_url = ""

        rows.append(
            {
                "item_title": meta.item_title,
                "skip_reason": meta.skip_reason,
                "matched_item_id": meta.item_id,
                "matched_item_label": matched_label,
                "matched_admin_url": matched_admin_url,
                "match_confidence": _match_confidence_for_reason(meta),
                "source_name": meta.source_name or "Unknown",
                "source_url": meta.source_url or "",
                "created_at": meta.created_at.isoformat(),
            }
        )

    return rows, ""


@login_required
@user_passes_test(is_admin)
def dashboard(request):
    """Render the staff scraping dashboard.

    Args:
        request: Django HttpRequest object.

    Returns:
        HttpResponse: Rendered dashboard template response.
    """
    _log_scraping_action(request)
    try:
        _ensure_default_scraping_sources()
    except Exception:
        logger.exception("Failed to seed default scraping sources")

    categories = []
    for key, meta in get_all_categories():
        last_run = (
            ScrapingRun.objects.filter(category=key).order_by("-started_at").first()
        )
        recent_runs = ScrapingRun.objects.filter(category=key).order_by("-started_at")[
            :5
        ]
        categories.append(
            {
                "key": key,
                "meta": meta,
                "last_run": last_run,
                "recent_runs": recent_runs,
            }
        )

    # Aggregate stats
    total_runs = ScrapingRun.objects.count()

    total_created = (
        ScrapingRun.objects.aggregate(total=Sum("items_created"))["total"] or 0
    )

    # Per-category item counts from actual models
    model_counts = {
        "events": Event.objects.count(),
        "tools": NLPTool.objects.count(),
        "news": Post.objects.count(),
        "courses": Course.objects.count(),
        "institutions": Institution.objects.count(),
    }
    pending_counts = {
        "events": Event.objects.filter(approval_status="pending").count(),
        "tools": NLPTool.objects.filter(approval_status="pending").count(),
        "news": Post.objects.filter(approval_status="pending").count(),
        "courses": Course.objects.filter(approval_status="pending").count(),
    }

    def _media_stats(queryset, image_field=None, pdf_field=None):
        total = queryset.count()
        with_images = (
            queryset.exclude(**{f"{image_field}": ""})
            .exclude(**{f"{image_field}__isnull": True})
            .count()
            if image_field
            else 0
        )
        with_pdfs = (
            queryset.exclude(**{f"{pdf_field}": ""})
            .exclude(**{f"{pdf_field}__isnull": True})
            .count()
            if pdf_field
            else 0
        )

        storage_bytes = 0
        media_fields = [f for f in [image_field, pdf_field] if f]
        for obj in queryset.only(*media_fields):
            for field_name in media_fields:
                file_obj = getattr(obj, field_name, None)
                file_name = getattr(file_obj, "name", "") if file_obj else ""
                if not file_name:
                    continue
                try:
                    full_path = file_obj.path
                    if os.path.exists(full_path):
                        storage_bytes += os.path.getsize(full_path)
                except (AttributeError, OSError, ValueError) as exc:
                    logger.warning(
                        "dashboard_media_stat_skipped_due_to_error",
                        extra={
                            "error": str(exc),
                            "context": f"item_id={getattr(obj, 'pk', None)}",
                        },
                        exc_info=False,
                    )
                    continue

        return {
            "with_images": with_images,
            "without_images": max(total - with_images, 0),
            "with_pdfs": with_pdfs,
            "without_pdfs": max(total - with_pdfs, 0),
            "storage_bytes": storage_bytes,
        }

    media_stats = {
        "events": _media_stats(
            Event.objects.all(), image_field="banner_image", pdf_field="attachment"
        ),
        "tools": _media_stats(
            NLPTool.objects.all(), image_field="thumbnail", pdf_field=None
        ),
        "news": _media_stats(
            Post.objects.all(), image_field="thumbnail", pdf_field="file"
        ),
        "courses": _media_stats(
            Course.objects.all(), image_field="thumbnail", pdf_field="uploaded_file"
        ),
        "institutions": _media_stats(
            Institution.objects.all(), image_field="logo", pdf_field=None
        ),
    }

    skip_analytics = _build_skip_reason_payload()
    source_health_rows = _build_source_health_rows()
    recent_runs_rows = {
        category_key: _build_recent_runs_rows(
            category_key,
            limit=SS.VIEW_RECENT_RUNS_LIMIT,
        )
        for category_key in CATEGORY_META
    }

    return render(
        request,
        "scraping/dashboard.html",
        {
            "categories": categories,
            "total_runs": total_runs,
            "total_created": total_created,
            "model_counts": model_counts,
            "pending_counts": pending_counts,
            "media_stats": media_stats,
            "skip_analytics": skip_analytics,
            "source_health_rows": source_health_rows,
            "recent_runs_rows": recent_runs_rows,
            "skip_analytics_json": json.dumps(skip_analytics),
            "source_health_rows_json": json.dumps(source_health_rows),
            "recent_runs_rows_json": json.dumps(recent_runs_rows),
            "page": "scraping",
        },
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def run_scraper(request, category):
    """Dispatch a scraper run asynchronously, with sync fallback.

    Args:
        request: Django HttpRequest object.
        category: Scraper category key.

    Returns:
        JsonResponse: Task start payload, fallback execution payload, or error.

    Raises:
        Exception: Internal task dispatch errors are handled and returned as JSON.
    """
    _log_scraping_action(request)
    staff_error = _require_staff(request)
    if staff_error:
        return staff_error

    if category not in CATEGORY_META:
        return JsonResponse(
            {"status": "error", "message": f"Unknown category: {category}"}, status=400
        )

    # Create a run log
    run = ScrapingRun.objects.create(
        category=category,
        status="running",
        triggered_by=request.user,
    )

    # --- Try async (Celery) execution first ---
    try:
        async_result = run_scraper_task.delay(
            category,
            run_id=str(run.pk),
            user_id=request.user.pk,
        )
        run.task_id = async_result.id
        run.save(update_fields=["task_id"])

        return JsonResponse(
            {
                "status": "started",
                "run_id": str(run.pk),
                "task_id": async_result.id,
                "message": "Scraper dispatched to background worker.",
            }
        )

    except Exception as celery_exc:
        # Celery unavailable — fall back to synchronous execution
        logger.warning(
            "Celery dispatch failed (%s), running %s synchronously",
            celery_exc,
            category,
        )

    # --- Synchronous fallback (original behaviour) ---
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

        return JsonResponse(
            {
                "status": "success",
                "run_id": str(run.pk),
                "items_found": run.items_found,
                "items_created": run.items_created,
                "items_skipped": run.items_skipped,
                "errors": result.get("errors", []),
                "results": result.get("results", []),
                "duration": run.duration,
            }
        )

    except Exception as exc:
        run.status = "failed"
        run.errors = str(exc)
        run.completed_at = timezone.now()
        run.save()
        logger.exception("Scraper %s failed", category)

        return JsonResponse(
            {
                "status": "error",
                "message": str(exc),
            },
            status=500,
        )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["polling"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="polling",
)
def run_scraper_status(request, run_id):
    """Poll the current status and results of a scraping run.

    Args:
        request: Django HttpRequest object.
        run_id: UUID string for the target ScrapingRun.

    Returns:
        JsonResponse: Current run state with counters and optional results.
    """
    _log_scraping_action(request)
    staff_error = _require_staff(request)
    if staff_error:
        return staff_error

    try:
        run = ScrapingRun.objects.get(pk=run_id)
    except ScrapingRun.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Run not found"}, status=404)

    data = {
        "status": run.status,
        "run_id": str(run.pk),
        "items_found": run.items_found,
        "items_created": run.items_created,
        "items_skipped": run.items_skipped,
        "duration": run.duration,
    }

    if run.status == "completed":
        # Fetch full results from the Celery result backend
        errors = run.errors.split("\n") if run.errors else []
        results = []
        if run.task_id:
            try:
                result = AsyncResult(run.task_id)
                if result.successful():
                    task_data = result.result or {}
                    results = task_data.get("results", [])
            except Exception as exc:
                logger.warning(
                    "run_status_result_fetch_failed",
                    extra={"error": str(exc), "context": str(run_id)},
                    exc_info=False,
                )
        data.update({"errors": errors, "results": results})
    elif run.status == "failed":
        data["errors"] = run.errors.split("\n") if run.errors else []
        data["message"] = run.errors

    return JsonResponse(data)


# Backward-compatible alias for existing URL names.
task_status = run_scraper_status


@login_required
@require_POST
@csrf_protect
@rate_limit(
    max_calls=RATE_LIMIT_MAP["action"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="action",
)
def run_custom_source(request, source_id):
    """AJAX endpoint: run the custom domain scraper for a single source."""
    _log_scraping_action(request)
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        source = ScrapingSource.objects.get(id=source_id, is_active=True)
    except ScrapingSource.DoesNotExist:
        return JsonResponse({"error": "Source not found"}, status=404)

    try:
        scraper = CustomDomainScraper(source)
        results = scraper.scrape()

        items_created = len(results)
        items_failed = getattr(scraper, "items_failed", 0)

        # Determine real status based on results
        if items_created == 0 and items_failed > 0:
            # Everything failed
            run_status = "failed"
        elif items_failed > 0:
            # Partial success
            run_status = "partial"
        else:
            # All items succeeded
            run_status = "success"

        source.last_scraped = timezone.now()
        source.last_run_status = run_status
        source.last_run_items_created = items_created
        source.last_run_error = (
            f"{items_failed} items failed to save" if items_failed > 0 else ""
        )
        source.save()

        return JsonResponse(
            {
                "success": items_created > 0 or items_failed == 0,
                "items_created": items_created,
                "items_failed": items_failed,
                "run_status": run_status,
                "source_name": source.name,
            }
        )
    except Exception as e:
        source.last_run_status = "failed"
        source.last_run_error = str(e)[:500]
        source.save()
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
            },
            status=500,
        )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def trends(request):
    """Return trend analytics over a requested month window.

    Args:
        request: Django HttpRequest object.

    Returns:
        JsonResponse: Trend metrics payload or error details.
    """
    _log_scraping_action(request)
    months = int(request.GET.get("months", 6))
    months = max(1, min(months, 24))  # clamp to 1-24

    try:
        data = detect_trends(months=months)
        return JsonResponse({"status": "ok", **data})
    except Exception as exc:
        logger.exception("Trend detection failed: %s", exc)
        return JsonResponse(
            {"status": "error", "message": str(exc)},
            status=500,
        )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def analytics(request):
    """Return aggregated scraping analytics for dashboard charts.

    Args:
        request: Django HttpRequest object.

    Returns:
        JsonResponse: Structured analytics grouped by category and media stats.
    """
    _log_scraping_action(request)

    by_category = {}
    skip_values = [choice[0] for choice in ScrapedItemMeta.SKIP_REASON_CHOICES]

    for category in CATEGORY_META:
        runs = ScrapingRun.objects.filter(category=category)
        completed = runs.filter(status="completed")
        total_runs = runs.count()
        total_saved = int(completed.aggregate(total=Sum("items_created"))["total"] or 0)
        total_skipped = int(
            completed.aggregate(total=Sum("items_skipped"))["total"] or 0
        )
        avg_duration = 0.0
        duration_values = []
        for run in completed.only("started_at", "completed_at"):
            if run.started_at and run.completed_at:
                duration_values.append(
                    (run.completed_at - run.started_at).total_seconds()
                )
        if duration_values:
            avg_duration = round(sum(duration_values) / len(duration_values), 2)

        skip_breakdown = {
            reason: ScrapedItemMeta.objects.filter(
                category=category,
                was_skipped=True,
                skip_reason=reason,
            ).count()
            for reason in skip_values
        }

        source_health = []
        for source in ScrapingSourceHealth.objects.filter(category=category).order_by(
            "source_name"
        ):
            source_health.append(
                {
                    "source": source.source_name,
                    "state": source.circuit_state,
                    "score": round(float(source.health_score) / 100.0, 4),
                }
            )

        last_completed = completed.aggregate(last_run_at=Max("started_at"))[
            "last_run_at"
        ]

        by_source = (
            ScrapedItemMeta.objects.filter(category=category, was_skipped=True)
            .values("source_name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        skip_by_source = [
            {"source": item["source_name"] or "Unknown", "count": item["count"]}
            for item in by_source
        ]

        by_category[category] = {
            "total_runs": total_runs,
            "total_saved": total_saved,
            "total_skipped": total_skipped,
            "skip_breakdown": skip_breakdown,
            "skip_by_source": skip_by_source,
            "avg_run_duration_seconds": avg_duration,
            "last_run_at": last_completed.isoformat() if last_completed else None,
            "source_health": source_health,
        }

    def _file_counts(queryset, image_field=None, pdf_field=None):
        images = 0
        pdfs = 0
        bytes_total = 0
        fields = [f for f in [image_field, pdf_field] if f]
        for obj in queryset.only(*fields):
            for field_name in fields:
                file_obj = getattr(obj, field_name, None)
                file_name = getattr(file_obj, "name", "") if file_obj else ""
                if not file_name:
                    continue
                lower_name = str(file_name).lower()
                if lower_name.endswith(".pdf"):
                    pdfs += 1
                else:
                    images += 1
                try:
                    path = getattr(file_obj, "path", "")
                    if path and os.path.exists(path):
                        bytes_total += os.path.getsize(path)
                except (AttributeError, OSError, ValueError) as exc:
                    logger.warning(
                        "analytics_media_count_skipped_due_to_error",
                        extra={
                            "error": str(exc),
                            "context": getattr(obj, "source_name", "unknown"),
                        },
                        exc_info=False,
                    )
                    continue
        return images, pdfs, bytes_total

    media_sets = [
        _file_counts(
            Event.objects.all(), image_field="banner_image", pdf_field="attachment"
        ),
        _file_counts(NLPTool.objects.all(), image_field="thumbnail", pdf_field=None),
        _file_counts(Post.objects.all(), image_field="thumbnail", pdf_field="file"),
        _file_counts(
            Course.objects.all(), image_field="thumbnail", pdf_field="uploaded_file"
        ),
        _file_counts(Institution.objects.all(), image_field="logo", pdf_field=None),
    ]
    total_images = sum(v[0] for v in media_sets)
    total_pdfs = sum(v[1] for v in media_sets)
    storage_bytes = sum(v[2] for v in media_sets)

    enrichment = {
        "total_enriched": ScrapedItemMeta.objects.filter(
            enrichment_status="complete"
        ).count(),
        "total_partial": ScrapedItemMeta.objects.filter(
            enrichment_status="partial"
        ).count(),
        "total_not_enriched": ScrapedItemMeta.objects.filter(
            enrichment_status="not_enriched"
        ).count(),
    }

    return JsonResponse(
        {
            "by_category": by_category,
            "media": {
                "total_images": total_images,
                "total_pdfs": total_pdfs,
                "storage_bytes": storage_bytes,
            },
            "enrichment": enrichment,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def skip_reason_analytics(request):
    """Chart-friendly skip reason breakdown by category and by source."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower() or None
    payload = _build_skip_reason_payload(category=category)
    return JsonResponse(payload)


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def source_health_summary(request):
    """Configured source health cards with tier, breaker state, and run throughput."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower() or None
    return JsonResponse(
        {
            "sources": _build_source_health_rows(category=category),
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def recent_runs(request):
    """Last 10 runs per category with status/duration and rerun URL."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower()
    if category and category not in CATEGORY_META:
        return JsonResponse({"error": "Unknown category"}, status=400)

    if category:
        return JsonResponse(
            {
                "category": category,
                "runs": _build_recent_runs_rows(
                    category,
                    limit=SS.VIEW_RECENT_RUNS_LIMIT,
                ),
            }
        )

    return JsonResponse(
        {
            "runs": {
                key: _build_recent_runs_rows(key, limit=SS.VIEW_RECENT_RUNS_LIMIT)
                for key in CATEGORY_META
            }
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["analytics"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="analytics",
)
def duplicates_preview(request):
    """List duplicate skips with matched admin item links and confidence."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower()
    if category not in CATEGORY_META:
        return JsonResponse(
            {"error": "category query param is required and must be valid"},
            status=400,
        )

    run_id = (request.GET.get("run_id") or "").strip() or None
    rows, error = _build_duplicate_preview(category, run_id=run_id)
    if rows is None:
        return JsonResponse({"error": error}, status=404)
    return JsonResponse({"category": category, "run_id": run_id, "duplicates": rows})


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def rerun_scraping_run(request, run_id):
    """Re-run a previous category run from Recent Runs table or admin action."""
    _log_scraping_action(request)
    original = ScrapingRun.objects.filter(pk=run_id).first()
    if original is None:
        return JsonResponse({"error": "Run not found"}, status=404)

    run = ScrapingRun.objects.create(
        category=original.category,
        status="running",
        triggered_by=request.user,
    )
    try:
        task = run_scraper_task.delay(
            original.category,
            run_id=str(run.pk),
            user_id=request.user.pk,
        )
        run.task_id = task.id
        run.save(update_fields=["task_id"])
        return JsonResponse(
            {
                "status": "started",
                "run_id": str(run.pk),
                "task_id": task.id,
                "category": original.category,
            }
        )
    except Exception as exc:
        run.status = "failed"
        run.errors = str(exc)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "errors", "completed_at"])
        return JsonResponse({"error": str(exc)}, status=500)


def _map_item_for_duplicate_check(category: str, item: dict) -> dict:
    title = (item.get("title") or item.get("name") or "").strip()
    description = (item.get("description") or "").strip()
    item_url = (item.get("url") or "").strip()

    if category == "events":
        return {
            "title_en": title,
            "website_url": item_url,
        }
    if category == "tools":
        return {
            "title_en": title,
            "access_link": item_url,
            "github_url": item.get("github_url") or "",
        }
    if category == "news":
        return {
            "title_en": title,
            "source_url": item_url,
            "doi": item.get("doi") or "",
            "arxiv_id": item.get("arxiv_id") or "",
        }
    if category == "courses":
        return {
            "title_en": title,
            "description_en": description,
            "access_link": item_url,
            "instructor": item.get("instructor") or "",
        }
    if category == "institutions":
        return {
            "name_en": title,
            "website_url": item_url,
            "ror_id": item.get("ror_id") or "",
        }
    return {"title_en": title}


def _run_source_test_job(job_id: str, source_id: str):
    try:
        source = ScrapingSource.objects.get(pk=source_id, is_active=True)
        scraper = CustomDomainScraper(source)

        stats = {
            "items_found": 0,
            "would_be_new": 0,
            "would_be_duplicate": 0,
            "preview": [],
            "status": "running",
            "error": "",
        }
        cache.set(
            f"scraping:source-test:{job_id}",
            stats,
            timeout=SS.SOURCE_TEST_CACHE_TTL,
        )

        original_save_item = scraper._save_item

        def _dry_run_save(item, category):
            mapped = _map_item_for_duplicate_check(category, item)
            reason = ""
            duplicate = False
            checker_map = {
                "events": scraper._dedup_event,
                "tools": scraper._dedup_tool,
                "news": scraper._dedup_news,
                "courses": scraper._dedup_course,
                "institutions": scraper._dedup_institution,
            }
            checker = checker_map.get(category)
            if checker is not None:
                duplicate, reason = checker(mapped)

            stats["items_found"] += 1
            if duplicate:
                stats["would_be_duplicate"] += 1
            else:
                stats["would_be_new"] += 1

            if len(stats["preview"]) < 50:
                stats["preview"].append(
                    {
                        "title": (item.get("title") or item.get("name") or "").strip(),
                        "duplicate": bool(duplicate),
                        "reason": reason,
                    }
                )
            cache.set(
                f"scraping:source-test:{job_id}",
                stats,
                timeout=SS.SOURCE_TEST_CACHE_TTL,
            )
            return item

        scraper._save_item = _dry_run_save  # type: ignore[assignment]
        scraper.scrape()
        scraper._save_item = original_save_item  # type: ignore[assignment]

        stats["status"] = "completed"
        cache.set(
            f"scraping:source-test:{job_id}",
            stats,
            timeout=SS.SOURCE_TEST_CACHE_TTL,
        )
    except Exception as exc:
        cache.set(
            f"scraping:source-test:{job_id}",
            {
                "status": "failed",
                "error": str(exc),
                "items_found": 0,
                "would_be_new": 0,
                "would_be_duplicate": 0,
                "preview": [],
            },
            timeout=SS.SOURCE_TEST_CACHE_TTL,
        )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def test_source(request, source_id):
    """Start one-source dry-run test and return a polling job id."""
    _log_scraping_action(request)
    source = ScrapingSource.objects.filter(pk=source_id, is_active=True).first()
    if source is None:
        return JsonResponse({"error": "Source not found"}, status=404)

    job_id = str(uuid.uuid4())
    cache.set(
        f"scraping:source-test:{job_id}",
        {
            "status": "running",
            "source_id": str(source.id),
            "source_name": source.name,
            "items_found": 0,
            "would_be_new": 0,
            "would_be_duplicate": 0,
            "preview": [],
        },
        timeout=SS.SOURCE_TEST_CACHE_TTL,
    )

    thread = threading.Thread(
        target=_run_source_test_job,
        args=(job_id, str(source.id)),
        daemon=True,
    )
    thread.start()

    return JsonResponse(
        {
            "status": "started",
            "job_id": job_id,
            "poll_url": reverse("scraping:test_source_status", args=[job_id]),
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(
    max_calls=RATE_LIMIT_MAP["polling"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="polling",
)
def test_source_status(request, job_id):
    """Poll one-source dry-run test status and preview counters."""
    _log_scraping_action(request)
    payload = cache.get(f"scraping:source-test:{job_id}")
    if payload is None:
        return JsonResponse({"error": "Job not found"}, status=404)
    return JsonResponse(payload)


def _build_human_message(network: dict, content: dict | None, category: str) -> str:
    http_response = network.get("http") or {}
    response_ms = http_response.get("response_ms")
    latency_text = f" ({response_ms}ms)" if isinstance(response_ms, int) else ""

    if network.get("overall") == "RED":
        reason = network.get("blocking_reason") or "UNKNOWN"
        return f"✗ Site inaccessible : {reason}"

    if not content:
        return f"⚠ Site accessible{latency_text} — Analyse de contenu indisponible"

    score = int(content.get("keyword_score") or 0)
    verdict = content.get("verdict")

    if verdict == "RELEVANT":
        return (
            f"✓ Site accessible{latency_text} — Contenu {category} detecte "
            f"(score: {score}%) — Pret a scraper"
        )

    if verdict == "UNCERTAIN":
        return (
            f"⚠ Site accessible{latency_text} mais contenu {category} incertain "
            f"(score: {score}%). Verification manuelle recommandee."
        )

    return (
        f"✗ Site accessible mais aucun contenu '{category}' trouve. "
        "Verifiez l'URL ou choisissez une autre categorie."
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def validate_source(request):
    """Validate source URL in two stages: network, then content relevance."""
    _log_scraping_action(request)
    url = (request.POST.get("url") or "").strip()
    category = (request.POST.get("category") or "").strip().lower()

    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)
    if category not in {"events", "news", "courses", "tools", "institutions"}:
        return JsonResponse({"error": "Invalid category"}, status=400)

    try:
        network = NetworkValidator(url).run()
    except Exception as exc:
        return JsonResponse(
            {
                "valid": False,
                "stage_failed": "network",
                "network": None,
                "content": None,
                "message": f"Network validation error: {exc}",
            },
            status=400,
        )

    if network.get("overall") == "RED":
        return JsonResponse(
            {
                "valid": False,
                "stage_failed": "network",
                "network": network,
                "content": None,
                "message": (
                    f"Site inaccessible : {network.get('blocking_reason') or 'UNKNOWN'}"
                ),
            }
        )

    try:
        content = ContentValidator(url, category).run()
    except Exception as exc:
        return JsonResponse(
            {
                "valid": False,
                "stage_failed": "content",
                "network": network,
                "content": None,
                "message": f"Content validation error: {exc}",
            },
            status=400,
        )

    valid = content.get("verdict") == "RELEVANT"
    return JsonResponse(
        {
            "valid": valid,
            "stage_failed": None if valid else "content",
            "network": network,
            "content": content,
            "message": _build_human_message(network, content, category),
        }
    )


@login_required
@require_POST
@csrf_protect
def add_custom_source(request):
    """AJAX endpoint: add a new custom scraping source (staff only)."""
    _log_scraping_action(request)
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    content_type_error = _require_json_content_type(request)
    if content_type_error:
        return content_type_error

    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        url = (data.get("url") or data.get("base_url") or "").strip()
        category = (data.get("category") or "").strip().lower()
        use_rss = data.get("use_rss", True)
        use_llm = data.get("use_llm_extraction", True)

        if not name or not url:
            return JsonResponse({"error": "Name and URL are required"}, status=400)

        if not url.startswith(("http://", "https://")):
            return JsonResponse({"error": "Invalid URL format"}, status=400)

        scrape_config = {}
        if not category:
            category = CustomDomainScraper.detect_category_from_signals(url, "")
            scrape_config["auto_detect_category"] = True
            scrape_config["detected_from_url"] = True

        source = ScrapingSource.objects.create(
            name=name,
            base_url=url,
            category=category,
            use_rss=use_rss,
            use_llm_extraction=use_llm,
            scrape_config=scrape_config,
            is_active=True,
        )
        return JsonResponse(
            {
                "success": True,
                "id": str(source.id),
                "name": source.name,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
@csrf_protect
def delete_custom_source(request, source_id):
    """AJAX endpoint: delete a custom scraping source (staff only)."""
    _log_scraping_action(request)
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        source = ScrapingSource.objects.get(id=source_id)
        name = source.name
        source.delete()
        return JsonResponse({"success": True, "name": name})
    except ScrapingSource.DoesNotExist:
        return JsonResponse({"error": "Source not found"}, status=404)


@login_required
@rate_limit(
    max_calls=RATE_LIMIT_MAP["action"],
    period_seconds=RATE_LIMIT_WINDOW_SECONDS,
    scope="action",
)
def list_custom_sources(request):
    """AJAX endpoint: list all active custom scraping sources (staff only)."""
    _log_scraping_action(request)
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    sources = ScrapingSource.objects.filter(is_active=True).order_by("-created_at")
    data = [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.base_url,
            "category": s.category,
            "category_display": s.get_category_display(),
            "is_default": bool((s.scrape_config or {}).get("is_default")),
            "last_scraped": s.last_scraped.isoformat() if s.last_scraped else None,
            "last_run_status": s.last_run_status,
            "last_run_items_created": s.last_run_items_created,
        }
        for s in sources
    ]
    return JsonResponse({"sources": data})


def _get_prometheus_allowed_networks() -> list:
    raw = getattr(settings, "PROMETHEUS_ALLOWED_NETWORKS", [])
    if isinstance(raw, str):
        entries = [part.strip() for part in raw.split(",") if part.strip()]
    else:
        entries = [str(part).strip() for part in raw if str(part).strip()]

    networks = []
    for cidr in entries:
        try:
            networks.append(ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Invalid PROMETHEUS_ALLOWED_NETWORKS CIDR: %s", cidr)
    return networks


def is_prometheus_request(request) -> bool:
    try:
        client_ip = ip_address(
            request.META.get(
                "HTTP_X_FORWARDED_FOR",
                request.META.get("REMOTE_ADDR", "0.0.0.0"),
            )
            .split(",")[0]
            .strip()
        )
        return any(
            client_ip in network for network in _get_prometheus_allowed_networks()
        )
    except ValueError:
        return False


def generate_latest_metrics_response():
    try:
        # Keep source health gauges fresh when scraped.
        update_source_health_metrics()
        update_scrape_queue_lag_metrics()
    except Exception:
        logger.exception("Failed to refresh source health metrics")

    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


@csrf_exempt
@require_GET
def scraping_metrics_view(request):
    """Prometheus metrics endpoint.

    - Allows unauthenticated access from Docker/internal allowlisted networks.
    - Requires authenticated staff access for all other source IPs.
    """
    _log_scraping_action(request)

    if is_prometheus_request(request):
        return generate_latest_metrics_response()

    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Authentication required for metrics access")

    ip = _client_ip(request)
    metrics_key = f"scraping:metrics:ip:{ip}"
    if not _enforce_rate_limit(
        metrics_key,
        limit=RATE_LIMIT_MAP["metrics"],
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    ):
        return JsonResponse(
            {
                "error": (
                    "Rate limit exceeded: "
                    f"max {RATE_LIMIT_MAP['metrics']} requests/"
                    f"{RATE_LIMIT_WINDOW_SECONDS}s."
                )
            },
            status=429,
        )

    return generate_latest_metrics_response()


# Backward-compatible name.
metrics_view = scraping_metrics_view
