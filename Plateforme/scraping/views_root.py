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
from datetime import timedelta
from ipaddress import ip_address, ip_network
from urllib.parse import urlencode

from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db.models import Count, Max, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST
from events.models import Event
from institutions.models import Institution
from feed.models import Post
from resources.models import Course, NLPTool

from scraping.intelligence import detect_trends
from scraping.scrapers.custom_scraper import CustomDomainScraper

from .metrics import update_scrape_queue_lag_metrics, update_source_health_metrics
from .models import ScrapedItemMeta, ScrapingRun, ScrapingSource, ScrapingSourceHealth
from .scrapers import CATEGORY_META, get_all_categories, get_scraper
from .tasks import run_scraper_task

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None


def rate_limit(max_calls: int, period_seconds: int, scope: str = "global"):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
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


DEFAULT_SCRAPING_SOURCES = {
    "events": [
        {"name": "WikiCFP", "url": "https://www.wikicfp.com"},
        {
            "name": "ConferenceAlerts (Algeria, Morocco, Tunisia, Egypt)",
            "url": "https://www.conferencealerts.com",
        },
        {
            "name": "AllConferenceAlert Algeria",
            "url": "https://www.allconferencealert.com/algeria.html",
        },
        {
            "name": "Curated NLP Conference List",
            "url": "https://aclanthology.org/events",
        },
        {
            "name": "Curated Arabic/MENA NLP Events",
            "url": "https://sigarab.github.io",
        },
    ],
    "tools": [
        {
            "name": "HuggingFace Model Hub API",
            "url": "https://huggingface.co/models",
        },
        {
            "name": "Curated Arabic LLMs & Speech Models",
            "url": "https://huggingface.co/models?language=ar",
        },
        {
            "name": "Curated HuggingFace Arabic Datasets",
            "url": "https://huggingface.co/datasets?language=ar",
        },
    ],
    "news": [
        {
            "name": "arXiv API (cs.CL)",
            "url": "http://export.arxiv.org/api/query?search_query=cat:cs.CL",
        },
        {
            "name": "Semantic Scholar API",
            "url": "https://api.semanticscholar.org/graph/v1/paper/search",
        },
    ],
    "courses": [
        {"name": "MIT OpenCourseWare", "url": "https://ocw.mit.edu"},
        {
            "name": "Coursera NLP Courses",
            "url": "https://www.coursera.org/search?query=nlp",
        },
        {
            "name": "YouTube NLP Playlists",
            "url": "https://www.youtube.com/results?search_query=nlp+playlist",
        },
        {
            "name": "Curated University Courses",
            "url": "https://www.edx.org/learn/natural-language-processing",
        },
    ],
    "institutions": [
        {"name": "ROR API", "url": "https://api.ror.org/organizations"},
        {"name": "OpenAlex API", "url": "https://api.openalex.org/institutions"},
        {
            "name": "Algerian Universities",
            "url": "https://www.mesrs.dz/en/universities",
        },
        {
            "name": "African & Arabic NLP Labs",
            "url": "https://deeplearningindaba.com",
        },
        {
            "name": "North African Institutions",
            "url": "https://www.auf.org/afrique-du-nord",
        },
        {
            "name": "Arabic/Gulf Institutions",
            "url": "https://www.gcc-sg.org/en-us/Pages/default.aspx",
        },
    ],
}


def _ensure_default_scraping_sources() -> None:
    """Ensure predefined default sources exist and stay active for each category."""
    for category, default_sources in DEFAULT_SCRAPING_SOURCES.items():
        for default_source in default_sources:
            name = (default_source.get("name") or "").strip()
            base_url = (default_source.get("url") or "").strip()
            if not name:
                continue

            source, created = ScrapingSource.objects.get_or_create(
                category=category,
                name=name,
                defaults={
                    "url": base_url,
                    "base_url": base_url,
                    "description": "Default source",
                    "is_active": True,
                    "scrape_config": {"is_default": True},
                    "use_rss": False,
                    "use_llm_extraction": True,
                },
            )

            update_fields = []
            if not getattr(source, "url", "") and base_url:
                source.url = base_url
                update_fields.append("url")
            if not source.base_url and base_url:
                source.base_url = base_url
                update_fields.append("base_url")
            if not source.is_active:
                source.is_active = True
                update_fields.append("is_active")

            scrape_config = dict(source.scrape_config or {})
            if scrape_config.get("is_default") is not True:
                scrape_config["is_default"] = True
                source.scrape_config = scrape_config
                update_fields.append("scrape_config")

            if created:
                continue

            if update_fields:
                source.save(update_fields=update_fields)


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
    if any(token in blob for token in (".dz", "alger", "algeria", "dgrsdt", "mesrs")):
        return 1
    if any(
        token in blob
        for token in (
            "arab",
            "mena",
            "morocco",
            "tunisia",
            "egypt",
            "saudi",
            "uae",
            "qatar",
            "jordan",
            "oman",
            "lebanon",
        )
    ):
        return 2
    if any(token in blob for token in ("africa", "african", "indaba", "masakhane")):
        return 3
    return 4


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def validate_source(request):
    """Temporary validation endpoint used by admin/source forms."""
    return JsonResponse(
        {
            "status": "success",
            "message": "Endpoint is working",
            "valid": True,
        }
    )


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
        "dedup_similarity": 85.0,
        "dedup_embedding": 70.0,
    }
    return fallback_map.get(meta.skip_reason, 75.0)


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
            reason = "dedup_similarity"
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


def _build_recent_runs_rows(category: str, limit: int = 10):
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
    """Main scraping dashboard — staff only."""
    _log_scraping_action(request)
    _ensure_default_scraping_sources()
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
        category_key: _build_recent_runs_rows(category_key, limit=10)
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


def _result_status_label(raw_status: str) -> str:
    if raw_status == "approved":
        return "VALIDATED"
    if raw_status == "rejected":
        return "REJECTED"
    return "PENDING"


def _result_status_badge(raw_status: str) -> str:
    if raw_status == "approved":
        return "success"
    if raw_status == "rejected":
        return "danger"
    return "warning"


def _scraping_result_category_map():
    return {
        "events": {
            "label": "Events",
            "model": Event,
            "title_field": "title",
            "description_field": "description",
            "source_field": "source_url",
            "date_field": "created_at",
            "status_field": "approval_status",
            "location_field": "location",
        },
        "news": {
            "label": "News",
            "model": Post,
            "title_field": "title",
            "description_field": "content",
            "source_field": "source_url",
            "date_field": "created_at",
            "status_field": "approval_status",
            "confidence_field": "relevance_score",
        },
        "tools": {
            "label": "Tools",
            "model": NLPTool,
            "title_field": "title",
            "description_field": "description",
            "source_field": "source_url",
            "date_field": "creation_date",
            "status_field": "approval_status",
            "entity_field": "use_cases",
        },
        "courses": {
            "label": "Courses",
            "model": Course,
            "title_field": "title",
            "description_field": "description",
            "source_field": "source_url",
            "date_field": "creation_date",
            "status_field": "approval_status",
            "entity_field": "keywords",
        },
        "institutions": {
            "label": "Institutions",
            "model": Institution,
            "title_field": "name",
            "description_field": "description",
            "source_field": "source_url",
            "date_field": "created_at",
            "status_field": "approval_status",
            "entity_field": "specialties",
            "location_field": "city",
        },
    }


def _is_scraped_item(obj, source_field: str) -> bool:
    value = getattr(obj, source_field, None)
    return bool(value)


def _resolve_scraping_item(item_id, requested_category: str | None = None):
    category_map = _scraping_result_category_map()
    category_candidates = []
    if requested_category and requested_category in category_map:
        category_candidates.append(requested_category)
    category_candidates.extend(
        [k for k in category_map.keys() if k != requested_category]
    )

    for cat_key in category_candidates:
        cfg = category_map[cat_key]
        model = cfg["model"]
        source_field = cfg["source_field"]
        obj = model.objects.filter(pk=item_id).first()
        if obj is None:
            continue
        if not _is_scraped_item(obj, source_field):
            continue
        return cat_key, cfg, obj
    return None, None, None


def _extract_ner_entities(obj, cfg, meta: ScrapedItemMeta | None):
    entity_values = []

    entity_field = cfg.get("entity_field")
    if entity_field:
        raw = getattr(obj, entity_field, None)
        if hasattr(raw, "all"):
            entity_values.extend([str(x) for x in raw.all()])
        elif isinstance(raw, str):
            entity_values.extend(
                [
                    part.strip()
                    for part in raw.replace(";", ",").split(",")
                    if part.strip()
                ]
            )
        elif isinstance(raw, list):
            entity_values.extend([str(x) for x in raw if x])

    if cfg.get("location_field"):
        loc = getattr(obj, cfg["location_field"], "")
        if loc:
            entity_values.append(str(loc))

    if meta and meta.domain_scores:
        entity_values.extend([str(k) for k in meta.domain_scores.keys() if k])

    # Keep insertion order while removing duplicates.
    return list(dict.fromkeys(entity_values))


def _apply_scraping_item_action(obj, cfg, action: str, user=None) -> int:
    if action == "delete":
        deleted_count, _ = obj.delete()
        return int(deleted_count)

    if action == "validate":
        model_field_names = {f.name for f in obj._meta.get_fields()}
        status_field = cfg["status_field"]
        setattr(obj, status_field, "approved")

        update_fields = [status_field]
        if "is_approved" in model_field_names:
            obj.is_approved = True
            update_fields.append("is_approved")
        if "approval_date" in model_field_names:
            obj.approval_date = timezone.now()
            update_fields.append("approval_date")
        if "approved_by" in model_field_names and user is not None:
            obj.approved_by = user
            update_fields.append("approved_by")

        obj.save(update_fields=update_fields)
        return 1

    return 0


def _results_redirect_url(
    category: str = "", query: str = "", run_id: str | None = None
) -> str:
    params = {}
    if category and category != "all":
        params["category"] = category
    if query:
        params["q"] = query
    if run_id:
        params["run_id"] = run_id
    url = reverse("scraping:scraping_results")
    if params:
        return f"{url}?{urlencode(params)}"
    return url


def _split_item_tokens(raw_values) -> list[str]:
    tokens = []
    for raw in raw_values:
        if raw is None:
            continue
        for token in str(raw).split(","):
            token = token.strip()
            if token:
                tokens.append(token)
    return tokens


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_result_validate(request, item_id):
    """POST /scraping/results/validate/<item_id>/."""
    _log_scraping_action(request)
    category_hint = (
        request.POST.get("category") or request.GET.get("category") or ""
    ).strip().lower() or None
    query = (request.POST.get("q") or request.GET.get("q") or "").strip()
    run_id = (request.POST.get("run_id") or request.GET.get("run_id") or "").strip()
    cat_key, cfg, obj = _resolve_scraping_item(item_id, category_hint)

    if not obj or not cfg or not cat_key:
        messages.error(request, "Scraped item not found.")
        return redirect(
            _results_redirect_url(category_hint or "", query, run_id=run_id)
        )

    affected = _apply_scraping_item_action(
        obj, cfg, action="validate", user=request.user
    )
    if affected:
        messages.success(request, "Item published successfully.")
    else:
        messages.warning(request, "No item was published.")

    return redirect(_results_redirect_url(cat_key, query, run_id=run_id))


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_result_delete(request, item_id):
    """POST /scraping/results/delete/<item_id>/."""
    _log_scraping_action(request)
    category_hint = (
        request.POST.get("category") or request.GET.get("category") or ""
    ).strip().lower() or None
    query = (request.POST.get("q") or request.GET.get("q") or "").strip()
    run_id = (request.POST.get("run_id") or request.GET.get("run_id") or "").strip()
    cat_key, cfg, obj = _resolve_scraping_item(item_id, category_hint)

    if not obj or not cfg or not cat_key:
        messages.error(request, "Scraped item not found.")
        return redirect(
            _results_redirect_url(category_hint or "", query, run_id=run_id)
        )

    affected = _apply_scraping_item_action(obj, cfg, action="delete", user=request.user)
    if affected:
        messages.success(request, "Item deleted successfully.")
    else:
        messages.warning(request, "No item was deleted.")

    return redirect(_results_redirect_url(cat_key, query, run_id=run_id))


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_results_bulk_action(request):
    """POST /scraping/results/bulk-action/ for validate/delete on multiple items."""
    _log_scraping_action(request)

    action = (request.POST.get("action") or "").strip().lower()
    category_hint = (request.POST.get("category") or "").strip().lower()
    query = (request.POST.get("q") or "").strip()
    run_id = (request.POST.get("run_id") or "").strip()

    item_tokens = _split_item_tokens(request.POST.getlist("item_ids"))
    if not item_tokens:
        item_tokens = _split_item_tokens(request.POST.getlist("selected_items"))

    if action not in {"validate", "delete"}:
        messages.warning(request, "Invalid bulk action.")
        return redirect(_results_redirect_url(category_hint, query, run_id=run_id))

    affected_total = 0
    for token in item_tokens:
        token_category = category_hint
        token_item_id = token
        if ":" in token:
            token_category, token_item_id = token.split(":", 1)
            token_category = token_category.strip().lower()
            token_item_id = token_item_id.strip()

        cat_key, cfg, obj = _resolve_scraping_item(
            token_item_id, token_category or None
        )
        if not obj or not cfg:
            continue
        affected_total += _apply_scraping_item_action(
            obj, cfg, action=action, user=request.user
        )

    if action == "validate":
        messages.success(request, f"Published {affected_total} selected item(s).")
    else:
        messages.success(request, f"Deleted {affected_total} selected item(s).")

    return redirect(_results_redirect_url(category_hint, query, run_id=run_id))


@login_required
@user_passes_test(is_admin)
def scraping_results(request):
    """Staff review queue for scraped items across categories."""
    _log_scraping_action(request)
    category_map = _scraping_result_category_map()

    selected_category = (request.GET.get("category") or "all").strip().lower()
    if selected_category != "all" and selected_category not in category_map:
        selected_category = "all"

    query = (request.GET.get("q") or "").strip()
    selected_run_id = (request.GET.get("run_id") or "").strip()
    selected_run = None

    if selected_run_id:
        selected_run = ScrapingRun.objects.filter(pk=selected_run_id).first()
        if selected_run is None:
            messages.warning(
                request,
                "Requested run was not found; showing unfiltered results.",
            )
            selected_run_id = ""
        else:
            selected_category = selected_run.category

    run_window_start = selected_run.started_at if selected_run else None
    run_window_end = None
    if selected_run:
        run_window_end = (selected_run.completed_at or timezone.now()) + timedelta(
            minutes=5
        )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        selected_items = request.POST.getlist("selected_items")
        posted_run_id = (request.POST.get("run_id") or "").strip()

        grouped_ids = defaultdict(list)
        for token in selected_items:
            if ":" not in token:
                continue
            cat_key, item_id = token.split(":", 1)
            cat_key = cat_key.strip().lower()
            item_id = item_id.strip()
            if cat_key in category_map and item_id:
                grouped_ids[cat_key].append(item_id)

        affected_total = 0
        for cat_key, ids in grouped_ids.items():
            cfg = category_map[cat_key]
            model = cfg["model"]
            source_field = cfg["source_field"]

            qs = model.objects.filter(pk__in=ids).exclude(
                **{f"{source_field}__isnull": True}
            )
            qs = qs.exclude(**{source_field: ""})

            for obj in qs:
                affected_total += _apply_scraping_item_action(
                    obj,
                    cfg,
                    action=action,
                    user=request.user,
                )

        if action == "validate":
            messages.success(request, f"Validated {affected_total} selected item(s).")
        elif action == "delete":
            messages.success(request, f"Deleted {affected_total} selected item(s).")
        else:
            messages.warning(request, "No valid bulk action was requested.")

        params = {}
        if selected_category and selected_category != "all":
            params["category"] = selected_category
        if query:
            params["q"] = query
        if posted_run_id:
            params["run_id"] = posted_run_id
        redirect_url = reverse("scraping:scraping_results")
        if params:
            redirect_url = f"{redirect_url}?{urlencode(params)}"
        return redirect(redirect_url)

    if selected_run:
        active_categories = [selected_run.category]
    elif selected_category == "all":
        active_categories = list(category_map.keys())
    else:
        active_categories = [selected_category]

    pending_counts = {}
    for cat_key, cfg in category_map.items():
        model = cfg["model"]
        source_field = cfg["source_field"]
        pending_qs = model.objects.filter(**{cfg["status_field"]: "pending"})
        pending_qs = pending_qs.exclude(**{f"{source_field}__isnull": True}).exclude(
            **{source_field: ""}
        )
        if (
            selected_run
            and cat_key == selected_run.category
            and run_window_start
            and run_window_end
        ):
            pending_qs = pending_qs.filter(
                **{
                    f"{cfg['date_field']}__gte": run_window_start,
                    f"{cfg['date_field']}__lte": run_window_end,
                }
            )
        elif selected_run and cat_key != selected_run.category:
            pending_qs = pending_qs.none()
        pending_counts[cat_key] = pending_qs.count()

    rows = []
    by_category_item_ids = defaultdict(list)
    by_category_titles = defaultdict(list)

    for cat_key in active_categories:
        cfg = category_map[cat_key]
        model = cfg["model"]
        title_field = cfg["title_field"]
        source_field = cfg["source_field"]
        date_field = cfg["date_field"]
        status_field = cfg["status_field"]

        queryset = model.objects.filter(**{status_field: "pending"})
        queryset = queryset.exclude(**{f"{source_field}__isnull": True}).exclude(
            **{source_field: ""}
        )

        if selected_run and run_window_start and run_window_end:
            queryset = queryset.filter(
                **{
                    f"{date_field}__gte": run_window_start,
                    f"{date_field}__lte": run_window_end,
                }
            )

        if query:
            queryset = queryset.filter(**{f"{title_field}__icontains": query})

        queryset = queryset.order_by(f"-{date_field}")

        for obj in queryset:
            title_value = getattr(obj, title_field, "") or ""
            source_value = getattr(obj, source_field, "") or ""
            date_value = getattr(obj, date_field, None)
            status_value = getattr(obj, status_field, "pending") or "pending"

            raw_confidence = None
            confidence_field = cfg.get("confidence_field")
            if confidence_field:
                raw_confidence = getattr(obj, confidence_field, None)

            item_id_str = str(obj.pk)
            by_category_item_ids[cat_key].append(item_id_str)
            if title_value:
                by_category_titles[cat_key].append(title_value)

            rows.append(
                {
                    "selection_key": f"{cat_key}:{item_id_str}",
                    "item_id": item_id_str,
                    "title": title_value,
                    "category": cat_key,
                    "category_label": cfg["label"],
                    "source_url": source_value,
                    "scraped_date": date_value,
                    "confidence_score": raw_confidence,
                    "status": _result_status_label(status_value),
                    "status_badge": _result_status_badge(status_value),
                    "detail_url": reverse(
                        "scraping:scraping_result_detail", args=[obj.pk]
                    )
                    + f"?category={cat_key}"
                    + (f"&run_id={selected_run_id}" if selected_run_id else ""),
                }
            )

    confidence_by_item = {}
    confidence_by_title = {}
    for cat_key in active_categories:
        ids = by_category_item_ids[cat_key]
        titles = by_category_titles[cat_key]
        if not ids and not titles:
            continue

        meta_q = ScrapedItemMeta.objects.filter(category=cat_key)
        filters = Q()
        if ids:
            filters |= Q(item_id__in=ids)
        if titles:
            filters |= Q(item_title__in=titles)

        for meta in meta_q.filter(filters).order_by("-updated_at", "-created_at"):
            if meta.relevance_score is None:
                continue
            score = round(float(meta.relevance_score), 2)
            if meta.item_id and meta.item_id not in confidence_by_item:
                confidence_by_item[meta.item_id] = score
            if meta.item_title and meta.item_title not in confidence_by_title:
                confidence_by_title[meta.item_title] = score

    for row in rows:
        if row["confidence_score"] is not None:
            row["confidence_score"] = round(float(row["confidence_score"]), 2)
            continue
        score = confidence_by_item.get(row["item_id"])
        if score is None:
            score = confidence_by_title.get(row["title"])
        row["confidence_score"] = score

    rows.sort(
        key=lambda r: (
            1 if r["scraped_date"] is not None else 0,
            str(r["scraped_date"] or ""),
        ),
        reverse=True,
    )

    latest_runs = {
        key: ScrapingRun.objects.filter(category=key).order_by("-started_at").first()
        for key in category_map
    }

    return render(
        request,
        "scraping/results.html",
        {
            "rows": rows,
            "selected_category": selected_category,
            "selected_run_id": selected_run_id,
            "selected_run": selected_run,
            "search_query": query,
            "category_tabs": [
                {
                    "key": key,
                    "label": cfg["label"],
                    "count": pending_counts[key],
                }
                for key, cfg in category_map.items()
            ],
            "pending_total": sum(pending_counts.values()),
            "latest_runs": latest_runs,
            "page": "scraping",
        },
    )


@login_required
@user_passes_test(is_admin)
def scraping_result_detail(request, item_id):
    """Detail page for one scraped item review with publish/delete actions."""
    _log_scraping_action(request)

    requested_category = (request.GET.get("category") or "").strip().lower() or None
    search_query = (request.GET.get("q") or "").strip()
    selected_run_id = (request.GET.get("run_id") or "").strip()
    cat_key, cfg, obj = _resolve_scraping_item(item_id, requested_category)
    if not obj or not cfg or not cat_key:
        raise Http404("Scraped review item not found")

    title_field = cfg["title_field"]
    description_field = cfg["description_field"]
    source_field = cfg["source_field"]
    date_field = cfg["date_field"]
    status_field = cfg["status_field"]

    title_value = getattr(obj, title_field, "") or ""
    description_value = getattr(obj, description_field, "") or ""
    source_url = getattr(obj, source_field, "") or ""
    scraped_date = getattr(obj, date_field, None)
    raw_status = getattr(obj, status_field, "pending") or "pending"
    location_value = ""
    if cfg.get("location_field"):
        location_value = getattr(obj, cfg["location_field"], "") or ""

    confidence_score = None
    confidence_field = cfg.get("confidence_field")
    if confidence_field:
        confidence_score = getattr(obj, confidence_field, None)

    meta = (
        ScrapedItemMeta.objects.filter(category=cat_key)
        .filter(Q(item_id=str(obj.pk)) | Q(item_title=title_value))
        .order_by("-updated_at", "-created_at")
        .first()
    )

    if confidence_score is None and meta and meta.relevance_score is not None:
        confidence_score = meta.relevance_score
    if confidence_score is not None:
        confidence_score = round(float(confidence_score), 2)

    ner_entities = _extract_ner_entities(obj, cfg, meta)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        affected = _apply_scraping_item_action(
            obj, cfg, action=action, user=request.user
        )

        if action == "validate" and affected:
            messages.success(request, "Item validated and published.")
            try:
                target_url = obj.get_absolute_url()
            except Exception:
                target_url = (
                    reverse("scraping:scraping_results") + f"?category={cat_key}"
                )
            return redirect(target_url)

        if action == "delete" and affected:
            messages.success(request, "Item deleted permanently.")
            back_url = reverse("scraping:scraping_results") + f"?category={cat_key}"
            return redirect(back_url)

        messages.warning(request, "No valid action was applied.")

    back_url = _results_redirect_url(cat_key, search_query, run_id=selected_run_id)
    validation_label = _result_status_label(raw_status)

    return render(
        request,
        "scraping/result_detail.html",
        {
            "item": obj,
            "item_id": str(obj.pk),
            "category": cat_key,
            "category_label": cfg["label"],
            "title": title_value,
            "description": description_value,
            "source_url": source_url,
            "scraped_date": scraped_date,
            "location": location_value,
            "ner_entities": ner_entities,
            "validation_label": validation_label,
            "validation_badge": _result_status_badge(raw_status),
            "confidence_score": confidence_score,
            "raw_url": source_url,
            "meta": meta,
            "back_url": back_url,
            "search_query": search_query,
            "selected_run_id": selected_run_id,
            "page": "scraping",
        },
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def run_scraper(request, category):
    """AJAX endpoint: dispatch a scraper as a Celery background task.

    Falls back to synchronous execution if Celery is unavailable.
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
@rate_limit(max_calls=60, period_seconds=60, scope="polling")
def run_scraper_status(request, run_id):
    """AJAX endpoint: poll the status of an asynchronous scraping run."""
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
@rate_limit(max_calls=5, period_seconds=60, scope="action")
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
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def trends(request):
    """AJAX endpoint: return trend analysis for the last N months."""
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
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def analytics(request):
    """Structured scraping analytics by category + media + enrichment."""
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
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def skip_reason_analytics(request):
    """Chart-friendly skip reason breakdown by category and by source."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower() or None
    payload = _build_skip_reason_payload(category=category)
    return JsonResponse(payload)


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
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
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
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
                "runs": _build_recent_runs_rows(category, limit=10),
            }
        )

    return JsonResponse(
        {"runs": {key: _build_recent_runs_rows(key, limit=10) for key in CATEGORY_META}}
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
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
        cache.set(f"scraping:source-test:{job_id}", stats, timeout=1800)

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
            cache.set(f"scraping:source-test:{job_id}", stats, timeout=1800)
            return item

        scraper._save_item = _dry_run_save  # type: ignore[assignment]
        scraper.scrape()
        scraper._save_item = original_save_item  # type: ignore[assignment]

        stats["status"] = "completed"
        cache.set(f"scraping:source-test:{job_id}", stats, timeout=1800)
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
            timeout=1800,
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
        timeout=1800,
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
@rate_limit(max_calls=60, period_seconds=60, scope="polling")
def test_source_status(request, job_id):
    """Poll one-source dry-run test status and preview counters."""
    _log_scraping_action(request)
    payload = cache.get(f"scraping:source-test:{job_id}")
    if payload is None:
        return JsonResponse({"error": "Job not found"}, status=404)
    return JsonResponse(payload)


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
        url = data.get("url", "").strip()
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
            url=url,
            base_url=url,
            category=category,
            use_rss=use_rss,
            use_llm_extraction=use_llm,
            scrape_config=scrape_config,
            is_active=True,
            source_type=data.get("source_type", "web"),
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
@rate_limit(max_calls=5, period_seconds=60, scope="action")
def list_custom_sources(request):
    """AJAX endpoint: list all active custom scraping sources (staff only)."""
    _log_scraping_action(request)
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    _ensure_default_scraping_sources()

    sources = ScrapingSource.objects.filter(is_active=True).order_by("-created_at")
    data = [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.url or s.base_url,
            "category": s.category,
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
    """Prometheus metrics endpoint with internal-network allowlist auth model.

    - Allows unauthenticated access from configured internal Docker networks.
    - Requires authenticated staff access for all other source IPs.
    """
    _log_scraping_action(request)

    if is_prometheus_request(request):
        return generate_latest_metrics_response()

    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Authentication required for metrics access")

    ip = _client_ip(request)
    metrics_key = f"scraping:metrics:ip:{ip}"
    if not _enforce_rate_limit(metrics_key, limit=10, window_seconds=60):
        return JsonResponse(
            {"error": "Rate limit exceeded: max 10 requests/minute."},
            status=429,
        )

    return generate_latest_metrics_response()


# Backward-compatible name used by urls.py exports.
metrics_view = scraping_metrics_view
