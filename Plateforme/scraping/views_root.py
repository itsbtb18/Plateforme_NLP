"""
Views for the Web Scraping module.

Supports both synchronous (fallback) and asynchronous (Celery) execution.
"""

import csv
import functools
import json
import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import date, timedelta
from ipaddress import ip_address, ip_network
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode, urlparse

import requests
from celery import current_app as current_celery_app
from celery.result import AsyncResult
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from events.models import Event
from feed.models import Post
from resources.models import Course, NLPTool

from scraping.extractors.core.llm_validation import GroqLLMClient
from scraping.intelligence import compute_relevance_score, detect_trends
from scraping.scrapers.custom_scraper import CustomDomainScraper
from scraping.validators.content_validator import ContentValidator
from scraping.validators.network_validator import NetworkValidator

from .metrics import update_scrape_queue_lag_metrics, update_source_health_metrics
from .models import (
    RejectedItem,
    ScrapedItemMeta,
    ScrapingNotification,
    ScrapingRun,
    ScrapingSource,
    ScrapingSourceHealth,
    SearchQuery,
)
from .scrapers import CATEGORY_META, get_all_categories, get_scraper
from .scraping_settings import scraping_settings as SS
from .tasks import (
    push_scraping_progress,
    run_quick_scrape_task,
    run_scraper_task,
    validate_source_async,
)
from .translation import ArabicTranslator

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - optional dependency guard
    BeautifulSoup = None

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None


_UUID_PATH_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_INT_SEGMENT_RE = re.compile(r"/\d+/")
_HASH_SEGMENT_RE = re.compile(r"/[a-f0-9]{32,}/", re.IGNORECASE)


def _get_path_template(path: str) -> str:
    """Convert dynamic URL paths to a stable endpoint template."""
    normalized = str(path or "/")
    normalized = _UUID_PATH_RE.sub("<uuid>", normalized)
    normalized = _INT_SEGMENT_RE.sub("/<id>/", normalized)
    normalized = _HASH_SEGMENT_RE.sub("/<hash>/", normalized)
    return normalized


def _rate_key(request, scope: str = "default") -> str:
    user_id = (
        request.user.id
        if request.user.is_authenticated and request.user.id is not None
        else "anon"
    )
    path_template = _get_path_template(request.path)
    return f"rl:{scope}:{user_id}:{path_template}"


def _check_rate_limit(request, scope: str, max_calls: int, period: int) -> bool:
    return _enforce_rate_limit(_rate_key(request, scope=scope), max_calls, period)


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Fail-open cache-backed rate limiter to avoid blocking on cache issues."""
    try:
        if cache.add(key, 1, timeout=window_seconds):
            return True
        current = cache.incr(key)
        return int(current) <= int(limit)
    except ValueError:
        # Key can expire between add/incr under concurrency; restart counter.
        cache.set(key, 1, timeout=window_seconds)
        return True
    except Exception as exc:
        logger.error("Rate limiter cache error: %s", exc)
        logger.warning(
            "RATE_LIMITER_CACHE_FAILURE: throttling may be degraded",
            extra={"error": str(exc), "key": key},
        )
        return True


def rate_limit(max_calls: int, period_seconds: int, scope: str = "global"):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not _check_rate_limit(request, scope, max_calls, period_seconds):
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


SCRAPING_NAV_CATEGORY_KEYS = (
    "events",
    "tools",
    "corpus",
    "opportunities",
    "courses",
    "news",
)


def _prompt_limit_for_category(_category: str) -> int:
    """Return the max active prompt limit applied to each category."""
    configured = int(getattr(SS, "PROMPT_MAX_ACTIVE_PER_CATEGORY", 20) or 20)
    return max(1, min(configured, 200))


def _active_prompt_count(category: str) -> int:
    return int(SearchQuery.objects.filter(category=category, is_active=True).count())


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
}


DEFAULT_SEARCH_QUERIES = {
    "events": [
        "upcoming Arabic NLP conferences",
        "NLP workshops in MENA",
    ],
    "tools": [
        "new Arabic NLP model releases",
        "open-source Arabic NLP tools",
    ],
    "courses": [
        "Arabic NLP online courses",
        "AI and NLP certification programs",
    ],
    "news": [
        "latest Arabic NLP research news",
        "recent NLP breakthroughs",
    ],
    "opportunities": [
        "Arabic NLP internships",
        "AI research fellowships",
    ],
    "corpus": [
        "new Arabic NLP datasets",
        "Arabic corpus benchmark releases",
    ],
}


def _ensure_default_scraping_sources() -> None:
    """
    Ensure default sources exist in DB.
    Never reactivate manually disabled or auto-quarantined sources.
    Only create missing sources and update non-critical metadata.
    """
    from scraping.fixtures.source_defaults import DEFAULT_SOURCES

    created_count = 0

    for source_data in DEFAULT_SOURCES:
        name = str(source_data.get("name") or "").strip()
        url = str(source_data.get("url") or "").strip()
        category = str(source_data.get("category") or "").strip().lower()

        if not name or not url or category not in CATEGORY_META:
            continue

        trust_score = float(source_data.get("trust_score", 0.8) or 0.8)
        source, created = ScrapingSource.objects.get_or_create(
            url=url,
            defaults={
                "name": name,
                "category": category,
                "base_url": url,
                "is_active": True,
                "is_admin_disabled": False,
                "scrape_config": {
                    "is_default": True,
                    "trust_score": round(max(0.0, min(1.0, trust_score)), 2),
                },
                "use_rss": False,
                "use_llm_extraction": True,
                "description": "Default source",
            },
        )

        if created:
            created_count += 1
            continue

        update_fields = []
        if source.name != name:
            source.name = name
            update_fields.append("name")
        if source.category != category:
            source.category = category
            update_fields.append("category")
        if not source.base_url:
            source.base_url = url
            update_fields.append("base_url")

        if update_fields:
            source.save(update_fields=update_fields)

    if created_count:
        logger.info("Created %s new default sources", created_count)


def _ensure_default_search_queries() -> None:
    """Ensure baseline search queries exist for all scraping dashboard categories."""
    for category, queries in DEFAULT_SEARCH_QUERIES.items():
        for query_text in queries:
            SearchQuery.objects.get_or_create(
                category=category,
                query_text=query_text,
                defaults={"is_active": True},
            )


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


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "on", "yes"}:
        return True
    if lowered in {"0", "false", "off", "no"}:
        return False
    return default


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
def validate_source(request, source_id=None):
    """Trigger asynchronous source validation and return task metadata."""
    _log_scraping_action(request)

    if not _check_rate_limit(
        request, scope="validate_source", max_calls=20, period=3600
    ):
        return JsonResponse(
            {"error": "Too many validation requests."},
            status=429,
            headers={"Retry-After": "3600"},
        )

    resolved_source_id = str(source_id or "").strip()

    if not resolved_source_id:
        if request.content_type and "application/json" in request.content_type.lower():
            try:
                payload = json.loads(request.body or b"{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            resolved_source_id = str(payload.get("source_id") or "").strip()
        else:
            resolved_source_id = str(request.POST.get("source_id") or "").strip()

    if not resolved_source_id:
        return JsonResponse({"error": "source_id is required"}, status=400)

    try:
        resolved_source_id = str(uuid.UUID(resolved_source_id))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid source_id format"}, status=400)

    source = ScrapingSource.objects.filter(id=resolved_source_id).only("id").first()
    if source is None:
        return JsonResponse({"error": "Source not found"}, status=404)

    try:
        task = validate_source_async.delay(str(source.id))
    except Exception as exc:
        logger.exception(
            "validate_source_dispatch_failed source_id=%s error=%s",
            resolved_source_id,
            exc,
        )
        return JsonResponse(
            {
                "status": "error",
                "source_id": resolved_source_id,
                "message": "Failed to dispatch source validation task",
            },
            status=500,
        )

    return JsonResponse(
        {
            "status": "validation_started",
            "source_id": resolved_source_id,
            "task_id": str(task.id),
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=60, period_seconds=60, scope="polling")
def validate_source_status(request, task_id):
    """Return Celery task status/result for an async source validation run."""
    _log_scraping_action(request)

    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        return JsonResponse({"error": "task_id is required"}, status=400)

    result = AsyncResult(normalized_task_id)
    state = str(result.state or "PENDING").upper()

    payload = {
        "task_id": normalized_task_id,
        "state": state,
    }

    if result.successful():
        payload.update(
            {
                "status": "completed",
                "ready": True,
                "result": result.result,
            }
        )
        return JsonResponse(payload)

    if result.failed():
        payload.update(
            {
                "status": "failed",
                "ready": True,
                "error": str(result.result),
            }
        )
        return JsonResponse(payload)

    if state == "STARTED":
        payload["status"] = "running"
    elif state == "RETRY":
        payload["status"] = "retrying"
    else:
        payload["status"] = "pending"

    payload["ready"] = False
    return JsonResponse(payload)


def _model_for_category(category: str):
    static_map = {
        "events": Event,
        "courses": Course,
        "tools": NLPTool,
    }
    if category in static_map:
        return static_map[category]

    dynamic_candidates = {
        "news": [("feed", "Post"), ("events", "News"), ("resources", "News")],
        "opportunities": [
            ("pages", "Opportunity"),
            ("events", "Opportunity"),
            ("resources", "Opportunity"),
        ],
        "corpus": [
            ("events", "Corpus"),
            ("resources", "Corpus"),
            ("corpus", "Corpus"),
        ],
    }
    for app_label, model_name in dynamic_candidates.get(category, []):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            continue
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


def _source_color_token(category: str) -> str:
    color_name = str((CATEGORY_META.get(category, {}) or {}).get("color") or "").lower()
    color_map = {
        "blue": "#2563eb",
        "purple": "#7c3aed",
        "green": "#059669",
        "yellow": "#ca8a04",
        "orange": "#ea580c",
        "red": "#dc2626",
    }
    return color_map.get(color_name, "#475569")


def _health_band_for_rate(success_rate: int | None) -> str:
    if success_rate is None:
        return "none"
    if success_rate >= 80:
        return "green"
    if success_rate >= 40:
        return "yellow"
    return "red"


def _priority_label_from_value(priority_value: int) -> str:
    if priority_value <= 2:
        return "high"
    if priority_value <= 4:
        return "medium"
    return "low"


def _extract_scrape_config_value(source: ScrapingSource, key: str, default=None):
    config = source.scrape_config if isinstance(source.scrape_config, dict) else {}
    if key not in config:
        return default
    return config.get(key)


def _build_source_health_points(source: ScrapingSource) -> tuple[list[dict], int]:
    last_runs = list(
        ScrapingRun.objects.filter(source=source).order_by("-started_at")[:10]
    )

    points = []
    success_count = 0

    for run in reversed(last_runs):
        state = "warn"
        if run.status == "failed":
            state = "fail"
        elif run.status == "completed":
            if int(run.items_created or 0) > 0:
                state = "ok"
            else:
                state = "warn"

        if state == "ok":
            success_count += 1

        points.append(
            {
                "state": state,
                "label": run.started_at.strftime("%Y-%m-%d %H:%M")
                if run.started_at
                else "",
                "items": int(run.items_created or 0),
                "status": run.status,
            }
        )

    if not points and source.last_run_status:
        fallback_state_map = {
            "success": "ok",
            "completed": "ok",
            "partial": "warn",
            "pending": "warn",
            "running": "warn",
            "failed": "fail",
        }
        fallback_state = fallback_state_map.get(source.last_run_status, "warn")
        if fallback_state == "ok":
            success_count = 1
        points.append(
            {
                "state": fallback_state,
                "label": source.last_scraped.strftime("%Y-%m-%d %H:%M")
                if source.last_scraped
                else "",
                "items": int(source.last_run_items_created or 0),
                "status": source.last_run_status,
            }
        )

    return points, success_count


def _build_source_row_payload(source: ScrapingSource) -> dict:
    health = ScrapingSourceHealth.objects.filter(
        category=source.category,
        source_name__iexact=source.name,
    ).first()

    points, success_count = _build_source_health_points(source)
    attempts = len(points)

    if attempts > 0 and source.last_scraped:
        success_rate = int(round((success_count / attempts) * 100))
    elif health and int(health.total_attempts or 0) > 0:
        success_rate = int(
            round(
                (int(health.total_successes or 0) / int(health.total_attempts or 1))
                * 100
            )
        )
    else:
        success_rate = None

    now = timezone.now()
    recent_runs_qs = ScrapingRun.objects.filter(
        source=source,
        started_at__gte=now - timedelta(days=30),
        status="completed",
    )
    avg_yield = recent_runs_qs.aggregate(avg=Avg("items_created")).get("avg")
    if avg_yield is None:
        avg_yield = source.last_run_items_created or 0

    trust_score = _extract_scrape_config_value(source, "trust_score", None)
    if trust_score is None and health and health.health_score is not None:
        trust_score = round(float(health.health_score) / 100.0, 2)
    if trust_score is None:
        trust_score = 0.8

    raw_priority = _extract_scrape_config_value(source, "priority", 3)
    try:
        priority_value = max(1, min(5, int(raw_priority)))
    except (TypeError, ValueError):
        priority_value = 3
    priority_label = _priority_label_from_value(priority_value)

    queries = _extract_scrape_config_value(source, "search_queries", [])
    if not isinstance(queries, list):
        queries = []
    cleaned_queries = [str(value).strip() for value in queries if str(value).strip()]

    consecutive_failures = int(
        (getattr(health, "consecutive_failures", 0) or 0)
        or (source.consecutive_failures or 0)
    )
    failing = consecutive_failures >= 3 or (
        success_rate is not None and success_rate < 40
        and (attempts >= 3 or int(getattr(health, "total_attempts", 0) or 0) >= 3)
    )

    last_run_at = source.last_scraped
    last_checked_at = source.last_validated_at or source.last_scraped

    return {
        "id": str(source.id),
        "name": source.name,
        "url": source.url or source.base_url,
        "category": source.category,
        "category_label": CATEGORY_META.get(source.category, {}).get(
            "label", source.category.title()
        ),
        "category_color": _source_color_token(source.category),
        "health_band": _health_band_for_rate(success_rate),
        "success_rate": success_rate,
        "consecutive_failures": consecutive_failures,
        "failing": failing,
        "health_points": points,
        "avg_yield": round(float(avg_yield or 0), 1),
        "last_run_at": last_run_at,
        "last_run_iso": last_run_at.isoformat() if last_run_at else "",
        "last_checked_at": last_checked_at,
        "last_checked_iso": last_checked_at.isoformat() if last_checked_at else "",
        "is_active": bool(source.is_active),
        "trust_score": round(float(trust_score), 2),
        "priority_value": priority_value,
        "priority_label": priority_label,
        "queries": cleaned_queries,
    }


def _load_arabic_nlp_fixture_payload() -> dict:
    fixture_path = (
        Path(settings.BASE_DIR) / "scraping" / "fixtures" / "arabic_nlp_sources.json"
    )
    if not fixture_path.exists():
        return {"sources": [], "query_templates": {}}

    try:
        with fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"sources": [], "query_templates": {}}

    if not isinstance(payload, dict):
        return {"sources": [], "query_templates": {}}

    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    query_templates = (
        payload.get("query_templates")
        if isinstance(payload.get("query_templates"), dict)
        else {}
    )

    return {
        "sources": sources,
        "query_templates": query_templates,
    }


def _clean_source_payload(data: dict) -> tuple[dict | None, str]:
    name = str(data.get("name") or "").strip()
    url = str(data.get("url") or "").strip()
    category = str(data.get("category") or "").strip().lower()
    source_id = str(data.get("source_id") or "").strip()

    if not name:
        return None, _("Source name is required.")
    if not url:
        return None, _("Source URL is required.")
    if not url.startswith(("http://", "https://")):
        return None, _("Source URL must start with http:// or https://")
    if category not in CATEGORY_META:
        return None, _("Invalid source category.")

    raw_queries = data.get("search_queries")
    query_list = raw_queries if isinstance(raw_queries, list) else []
    cleaned_queries = [str(value).strip() for value in query_list if str(value).strip()]

    raw_priority = data.get("priority", 3)
    if isinstance(raw_priority, str):
        lowered = raw_priority.strip().lower()
        priority_lookup = {"high": 1, "medium": 3, "low": 5}
        raw_priority = priority_lookup.get(lowered, raw_priority)
    try:
        priority_value = max(1, min(5, int(raw_priority)))
    except (TypeError, ValueError):
        priority_value = 3

    try:
        trust_score = float(data.get("trust_score", 0.8))
    except (TypeError, ValueError):
        trust_score = 0.8
    trust_score = max(0.0, min(1.0, trust_score))

    payload = {
        "source_id": source_id,
        "name": name,
        "url": url,
        "category": category,
        "source_type": str(data.get("source_type") or "web").strip().lower() or "web",
        "use_rss": _as_bool(data.get("use_rss"), default=True),
        "use_llm_extraction": _as_bool(data.get("use_llm_extraction"), default=True),
        "is_active": _as_bool(data.get("is_active"), default=True),
        "priority": priority_value,
        "trust_score": round(trust_score, 2),
        "search_queries": cleaned_queries,
    }
    return payload, ""


def _save_source_payload(data: dict) -> tuple[ScrapingSource | None, bool, str]:
    payload, error = _clean_source_payload(data)
    if payload is None:
        return None, False, error

    source = None
    created = False
    source_id = payload["source_id"]
    if source_id:
        source = ScrapingSource.objects.filter(id=source_id).first()
        if source is None:
            return None, False, _("Source not found.")
    else:
        source = ScrapingSource()
        created = True

    scrape_config = (
        source.scrape_config if isinstance(source.scrape_config, dict) else {}
    )
    scrape_config.update(
        {
            "priority": payload["priority"],
            "trust_score": payload["trust_score"],
            "search_queries": payload["search_queries"],
        }
    )

    source.name = payload["name"]
    source.url = payload["url"]
    source.base_url = payload["url"]
    source.category = payload["category"]
    source.source_type = payload["source_type"]
    source.use_rss = payload["use_rss"]
    source.use_llm_extraction = payload["use_llm_extraction"]
    if "is_active" in data:
        source.is_active = payload["is_active"]
        source.is_admin_disabled = not bool(payload["is_active"])
    source.scrape_config = scrape_config
    source.save()

    return source, created, ""


def _build_recent_runs_rows(category: str, limit: int = 10):
    runs = ScrapingRun.objects.filter(category=category).order_by("-started_at")[:limit]
    output = []
    for run in runs:
        output.append(
            {
                "run_id": str(run.id),
                "status": run.status,
                "run_mode": (
                    "quick"
                    if str(run.current_source or "").strip().lower() == "quick_scrape"
                    else "standard"
                ),
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

    try:
        _ensure_default_search_queries()
    except DatabaseError as exc:
        logger.warning(
            "dashboard_seed_search_queries_failed",
            extra={"error": str(exc), "context": "default_queries"},
            exc_info=False,
        )

    dashboard_categories = (
        "events",
        "tools",
        "corpus",
        "opportunities",
        "courses",
        "news",
    )

    category_meta_map = {key: meta for key, meta in get_all_categories()}

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        allowed_categories = set(dashboard_categories)

        if action == "add_search_query":
            category = (request.POST.get("category") or "").strip().lower()
            query_text = (request.POST.get("query_text") or "").strip()
            is_active = _as_bool(request.POST.get("is_active"), default=False)

            if category in allowed_categories and query_text:
                try:
                    query_obj, created = SearchQuery.objects.get_or_create(
                        category=category,
                        query_text=query_text,
                        defaults={"is_active": is_active},
                    )
                    if not created and query_obj.is_active != is_active:
                        query_obj.is_active = is_active
                        query_obj.save(update_fields=["is_active"])
                except DatabaseError as exc:
                    logger.warning(
                        "dashboard_add_search_query_failed",
                        extra={"error": str(exc), "context": category},
                        exc_info=False,
                    )

        elif action == "toggle_search_query":
            query_id = (request.POST.get("query_id") or "").strip()
            is_active = _as_bool(request.POST.get("is_active"), default=False)

            if query_id:
                try:
                    SearchQuery.objects.filter(
                        id=query_id,
                        category__in=dashboard_categories,
                    ).update(is_active=is_active)
                except DatabaseError as exc:
                    logger.warning(
                        "dashboard_toggle_search_query_failed",
                        extra={"error": str(exc), "context": query_id},
                        exc_info=False,
                    )

    categories = []
    for key in dashboard_categories:
        meta = (
            category_meta_map.get(key)
            or CATEGORY_META.get(key)
            or {
                "label": key.title(),
                "description": "",
                "icon": "fa-circle",
                "color": "#2563eb",
            }
        )
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
    total_runs = ScrapingRun.objects.filter(category__in=dashboard_categories).count()

    total_created = (
        ScrapingRun.objects.filter(category__in=dashboard_categories).aggregate(
            total=Sum("items_created")
        )["total"]
        or 0
    )
    models_by_category = {
        category_key: _model_for_category(category_key)
        for category_key in dashboard_categories
    }

    def _model_field_names(model_cls):
        return {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }

    def _count_pending(model_cls):
        if model_cls is None:
            return 0
        field_names = _model_field_names(model_cls)
        if "approval_status" in field_names:
            return model_cls.objects.filter(approval_status="pending").count()
        if "is_approved" in field_names:
            return model_cls.objects.filter(is_approved=False).count()
        return 0

    model_counts = {}
    pending_counts = {}
    for category_key in dashboard_categories:
        model_cls = models_by_category.get(category_key)
        if model_cls is None:
            model_counts[category_key] = 0
            pending_counts[category_key] = 0
            continue
        model_counts[category_key] = model_cls.objects.count()
        pending_counts[category_key] = _count_pending(model_cls)

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
        if media_fields:
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

    def _first_existing_field(field_names, *candidates):
        for candidate in candidates:
            if candidate in field_names:
                return candidate
        return None

    def _category_media_stats(category_key):
        model_cls = models_by_category.get(category_key)
        if model_cls is None:
            return {
                "with_images": 0,
                "without_images": 0,
                "with_pdfs": 0,
                "without_pdfs": 0,
                "storage_bytes": 0,
            }

        field_names = _model_field_names(model_cls)
        preferred_fields = {
            "events": ("banner_image", "attachment"),
            "tools": ("thumbnail", None),
            "courses": ("thumbnail", "uploaded_file"),
            "news": ("thumbnail", "file"),
            "opportunities": (None, None),
            "corpus": ("thumbnail", "uploaded_file"),
        }
        image_field, pdf_field = preferred_fields.get(category_key, (None, None))

        if image_field not in field_names:
            image_field = _first_existing_field(
                field_names,
                "thumbnail",
                "image",
                "banner_image",
                "logo",
                "icon",
                "cover_image",
            )
        if pdf_field not in field_names:
            pdf_field = _first_existing_field(
                field_names,
                "file",
                "uploaded_file",
                "attachment",
                "pdf_file",
                "document",
                "document_file",
            )

        return _media_stats(
            model_cls.objects.all(),
            image_field=image_field,
            pdf_field=pdf_field,
        )

    media_stats = {
        category_key: _category_media_stats(category_key)
        for category_key in dashboard_categories
    }

    skip_analytics_raw = _build_skip_reason_payload()
    skip_analytics = {
        "per_category": {
            category_key: skip_analytics_raw.get("per_category", {}).get(
                category_key, {}
            )
            for category_key in dashboard_categories
            if skip_analytics_raw.get("per_category", {}).get(category_key)
        },
        "per_source": {
            category_key: skip_analytics_raw.get("per_source", {}).get(category_key, {})
            for category_key in dashboard_categories
            if skip_analytics_raw.get("per_source", {}).get(category_key)
        },
    }

    # Source URL inventory is intentionally ignored in the new query-first dashboard.
    source_health_rows = []
    recent_runs_rows = {
        category_key: _build_recent_runs_rows(category_key, limit=10)
        for category_key in dashboard_categories
    }

    search_query_category_choices = [
        (
            category_key,
            str(
                (
                    category_meta_map.get(category_key)
                    or CATEGORY_META.get(category_key)
                    or {}
                ).get("label", category_key.title())
            ),
        )
        for category_key in dashboard_categories
    ]

    search_queries_by_category = {
        category_key: [] for category_key in dashboard_categories
    }
    search_query_rows = []
    try:
        search_query_qs = SearchQuery.objects.filter(
            category__in=dashboard_categories
        ).order_by("category", "id")
        for query in search_query_qs:
            category_key = query.category
            category_label = str(
                (
                    category_meta_map.get(category_key)
                    or CATEGORY_META.get(category_key)
                    or {}
                ).get("label", category_key.title())
            )
            search_query_rows.append(
                {
                    "id": str(query.id),
                    "category": category_key,
                    "category_label": category_label,
                    "query_text": query.query_text,
                    "is_active": bool(query.is_active),
                }
            )
            if query.is_active:
                search_queries_by_category.setdefault(category_key, []).append(
                    query.query_text
                )
    except DatabaseError as exc:
        logger.warning(
            "dashboard_search_queries_load_failed",
            extra={"error": str(exc), "context": "search_queries"},
            exc_info=False,
        )

    review_supported_categories = list(_scraping_result_category_map().keys())

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
            "search_queries_by_category": search_queries_by_category,
            "search_query_rows": search_query_rows,
            "search_query_category_choices": search_query_category_choices,
            "skip_analytics_json": json.dumps(skip_analytics),
            "source_health_rows_json": json.dumps(source_health_rows),
            "recent_runs_rows_json": json.dumps(recent_runs_rows),
            "search_queries_by_category_json": json.dumps(search_queries_by_category),
            "search_query_rows_json": json.dumps(search_query_rows),
            "review_supported_categories": review_supported_categories,
            "review_supported_categories_json": json.dumps(review_supported_categories),
            "page": "scraping",
            **_scraping_shell_context(request, active_page="dashboard"),
        },
    )


# Public alias used by URL configuration for consistency with other scraping pages.
scraping_dashboard = dashboard


def scraping_dashboard_by_category(request, category: str):
    category_key = _set_category_request_context(request, category)

    category_cfg = _scraping_result_category_map().get(category_key, {})
    model_cls = category_cfg.get("model")
    status_field = category_cfg.get("status_field")

    kpi_scraped = 0
    kpi_pending = 0
    kpi_approved = 0

    if model_cls is not None:
        kpi_scraped = int(model_cls.objects.count())
        if status_field:
            try:
                kpi_pending = int(
                    model_cls.objects.filter(**{status_field: "pending"}).count()
                )
                kpi_approved = int(
                    model_cls.objects.filter(**{status_field: "approved"}).count()
                )
            except Exception:
                kpi_pending = 0
                kpi_approved = 0

    total_for_rate = kpi_pending + kpi_approved
    kpi_success_rate = (
        f"{round((kpi_approved / total_for_rate) * 100)}%"
        if total_for_rate > 0
        else "0%"
    )

    ai_prompts = list(
        SearchQuery.objects.filter(category=category_key, is_active=True)
        .order_by("id")
        .values("id", "query_text", "is_active")
    )
    max_active_prompts = _prompt_limit_for_category(category_key)
    active_prompt_count = len(ai_prompts)
    prompt_slots_remaining = max(0, max_active_prompts - active_prompt_count)

    recent_runs = ScrapingRun.objects.filter(category=category_key).order_by(
        "-started_at"
    )[:10]
    recent_run_snapshots = [
        {
            "run_id": str(run.id)[:8],
            "started_at": run.started_at.strftime("%Y-%m-%d %H:%M")
            if run.started_at
            else "-",
            "duration": (f"{int(run.duration)}s" if run.duration is not None else "-"),
            "items_created": int(run.items_created or 0),
            "items_updated": int(run.items_updated or 0),
            "items_skipped": int(run.items_skipped or 0),
            "status": str(run.status or "-").upper(),
            "run_mode": (
                "quick"
                if str(run.current_source or "").strip().lower() == "quick_scrape"
                else "standard"
            ),
        }
        for run in recent_runs
    ]

    latest_run = recent_runs[0] if recent_runs else None
    last_run_status = (
        str(getattr(latest_run, "status", "") or "").replace("_", " ").upper()
        if latest_run is not None
        else str(_("No run yet"))
    )
    last_run_time = (
        latest_run.started_at.strftime("%Y-%m-%d %H:%M")
        if latest_run is not None and latest_run.started_at
        else ""
    )

    category_name = str(
        _(
            (CATEGORY_META.get(category_key, {}) or {}).get(
                "label", category_key.title()
            )
        )
    )
    is_rtl_lang = str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar")

    def ui(en_text: str, ar_text: str) -> str:
        return ar_text if is_rtl_lang else str(_(en_text))

    context = {
        "page": "scraping",
        "category_key": category_key,
        "category_name": category_name,
        "category_active_tab": "dashboard",
        "category_global_status": "ok" if latest_run is not None else "warn",
        "category_global_status_label": (
            str(_("Global status: OK"))
            if latest_run is not None
            else str(_("Global status: No runs yet"))
        ),
        "kpi_scraped": kpi_scraped,
        "kpi_pending": kpi_pending,
        "kpi_approved": kpi_approved,
        "kpi_success_rate": kpi_success_rate,
        "ai_prompts": ai_prompts,
        "max_active_prompts": max_active_prompts,
        "active_prompt_count": active_prompt_count,
        "prompt_slots_remaining": prompt_slots_remaining,
        "last_run_status": last_run_status,
        "last_run_time": last_run_time,
        "recent_run_snapshots": recent_run_snapshots,
        **_scraping_shell_context(request, active_page="dashboard"),
    }
    return render(request, "scraping/category_dashboard.html", context)


def scraping_results_by_category(request, category: str):
    _set_category_request_context(request, category)
    return scraping_results(request)


def scraping_analytics_by_category(request, category: str):
    _set_category_request_context(request, category)
    return scraping_analytics_page(request)


def scraping_sources_by_category(request, category: str):
    _set_category_request_context(request, category)
    return scraping_sources_page(request)


def scraping_settings_by_category(request, category: str):
    _set_category_request_context(request, category)
    return scraping_settings_page(request)


@login_required
@user_passes_test(is_admin)
@require_GET
def scraping_settings_page(request):
    """Render a category-aware scraping settings page with live configuration data."""
    _log_scraping_action(request)

    category_key = _resolve_scraping_nav_category(request)
    category_name = str(
        _(
            (CATEGORY_META.get(category_key, {}) or {}).get(
                "label", category_key.title()
            )
        )
    )
    is_rtl_lang = str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar")

    def ui(en_text: str, ar_text: str) -> str:
        return ar_text if is_rtl_lang else str(_(en_text))

    category_sources_qs = ScrapingSource.objects.filter(category=category_key)
    all_sources_qs = ScrapingSource.objects.all()

    source_stats = {
        "total": int(category_sources_qs.count()),
        "active": int(category_sources_qs.filter(is_active=True).count()),
        "inactive": int(category_sources_qs.filter(is_active=False).count()),
        "rss_enabled": int(category_sources_qs.filter(use_rss=True).count()),
        "llm_enabled": int(category_sources_qs.filter(use_llm_extraction=True).count()),
        "ssl_disabled": int(category_sources_qs.filter(verify_ssl=False).count()),
        "proxy_enabled": int(
            category_sources_qs.exclude(proxy_url__isnull=True)
            .exclude(proxy_url="")
            .count()
        ),
        "global_total": int(all_sources_qs.count()),
        "global_active": int(all_sources_qs.filter(is_active=True).count()),
    }

    schedule_tier_labels = {
        "very_high": ui("Very High", "عال جدا"),
        "high": ui("High", "عال"),
        "medium": ui("Medium", "متوسط"),
        "low": ui("Low", "منخفض"),
        "dormant": ui("Dormant", "خامل"),
    }
    schedule_tier_counts = {
        key: int(category_sources_qs.filter(schedule_tier=key).count())
        for key in schedule_tier_labels
    }
    schedule_tier_rows = [
        {
            "key": tier_key,
            "label": tier_label,
            "count": schedule_tier_counts.get(tier_key, 0),
        }
        for tier_key, tier_label in schedule_tier_labels.items()
    ]

    validation_counts = {
        "GREEN": int(category_sources_qs.filter(validation_status="GREEN").count()),
        "YELLOW": int(category_sources_qs.filter(validation_status="YELLOW").count()),
        "RED": int(category_sources_qs.filter(validation_status="RED").count()),
        "PENDING": int(category_sources_qs.filter(validation_status="PENDING").count()),
        "UNKNOWN": int(category_sources_qs.filter(validation_status="UNKNOWN").count()),
    }

    source_rows = []
    for source in category_sources_qs.order_by("name")[:40]:
        source_rows.append(
            {
                "id": str(source.id),
                "name": source.name,
                "url": source.base_url or source.url,
                "is_active": bool(source.is_active),
                "use_rss": bool(source.use_rss),
                "use_llm_extraction": bool(source.use_llm_extraction),
                "verify_ssl": bool(source.verify_ssl),
                "has_proxy": bool(str(source.proxy_url or "").strip()),
                "schedule_tier": str(source.schedule_tier or "medium"),
                "schedule_interval_hours": int(source.schedule_interval_hours or 0),
                "validation_status": str(source.validation_status or "UNKNOWN"),
                "last_run_status": str(source.last_run_status or "pending"),
                "last_run_items_created": int(source.last_run_items_created or 0),
                "last_scraped": source.last_scraped,
                "consecutive_failures": int(source.consecutive_failures or 0),
            }
        )

    query_rows = list(
        SearchQuery.objects.filter(category=category_key)
        .order_by("-is_active", "query_text")
        .values("id", "query_text", "is_active")[:40]
    )
    active_query_count = sum(1 for row in query_rows if row.get("is_active"))

    bool_yes = ui("Yes", "نعم")
    bool_no = ui("No", "لا")

    settings_sections = [
        {
            "title": ui("Timeouts", "مهلات الاتصال"),
            "items": [
                {
                    "label": ui("Connect timeout", "مهلة الاتصال"),
                    "value": f"{SS.CONNECT_TIMEOUT}s",
                    "hint": ui(
                        "Maximum time to open a TCP connection.",
                        "الحد الأقصى لفتح اتصال TCP.",
                    ),
                },
                {
                    "label": ui("Read timeout", "مهلة القراءة"),
                    "value": f"{SS.READ_TIMEOUT}s",
                    "hint": ui(
                        "Maximum wait time for response body.",
                        "الحد الأقصى لانتظار محتوى الاستجابة.",
                    ),
                },
                {
                    "label": ui("Total request timeout", "المهلة الكلية للطلب"),
                    "value": f"{SS.TOTAL_TIMEOUT}s",
                    "hint": ui(
                        "Hard cap per outbound request.",
                        "حد أقصى صارم لكل طلب خارجي.",
                    ),
                },
                {
                    "label": ui("LLM timeout", "مهلة LLM"),
                    "value": f"{SS.LLM_TIMEOUT}s",
                    "hint": ui(
                        "Maximum wait time for LLM calls.",
                        "الحد الأقصى لانتظار استدعاءات LLM.",
                    ),
                },
            ],
        },
        {
            "title": ui("Retry & Backoff", "إعادة المحاولة والتراجع"),
            "items": [
                {
                    "label": ui("Max retries", "أقصى عدد للمحاولات"),
                    "value": str(SS.MAX_RETRIES),
                    "hint": ui(
                        "Maximum retry attempts per request.",
                        "أقصى محاولات إعادة لكل طلب.",
                    ),
                },
                {
                    "label": ui("Backoff base", "قاعدة التراجع"),
                    "value": f"{SS.RETRY_BACKOFF_BASE}s",
                    "hint": ui(
                        "Initial delay used for exponential backoff.",
                        "التأخير الابتدائي المستخدم في التراجع الأسي.",
                    ),
                },
                {
                    "label": ui("Backoff cap", "الحد الأعلى للتراجع"),
                    "value": f"{SS.RETRY_BACKOFF_CAP}s",
                    "hint": ui(
                        "Maximum delay between retries.",
                        "أقصى تأخير بين المحاولات.",
                    ),
                },
            ],
        },
        {
            "title": ui("Deduplication", "إزالة التكرار"),
            "items": [
                {
                    "label": ui("Jaccard threshold", "عتبة جاكارد"),
                    "value": str(SS.JACCARD_THRESHOLD),
                    "hint": ui(
                        "Loose textual similarity threshold.",
                        "عتبة تشابه نصي مرن.",
                    ),
                },
                {
                    "label": ui("Strict Jaccard", "جاكارد الصارم"),
                    "value": str(SS.STRICT_JACCARD),
                    "hint": ui(
                        "Strict textual similarity threshold.",
                        "عتبة تشابه نصي صارمة.",
                    ),
                },
                {
                    "label": ui("Semantic fallback", "البديل الدلالي"),
                    "value": str(SS.SEMANTIC_FALLBACK),
                    "hint": ui(
                        "Cosine similarity fallback threshold.",
                        "عتبة بديل تشابه جيب التمام.",
                    ),
                },
                {
                    "label": ui("Dedup window", "نافذة إزالة التكرار"),
                    "value": str(SS.DEDUP_WINDOW),
                    "hint": ui(
                        "Recent records scanned for duplicates.",
                        "السجلات الحديثة المفحوصة لاكتشاف التكرار.",
                    ),
                },
            ],
        },
        {
            "title": ui("System Limits", "حدود النظام"),
            "items": [
                {
                    "label": ui("RSS max items", "الحد الأقصى لعناصر RSS"),
                    "value": str(SS.RSS_MAX_ITEMS),
                    "hint": ui(
                        "Maximum entries fetched from RSS feeds.",
                        "أقصى عناصر يتم جلبها من RSS.",
                    ),
                },
                {
                    "label": ui("Concurrent downloads", "التنزيلات المتزامنة"),
                    "value": str(SS.MAX_CONCURRENT_DOWNLOADS),
                    "hint": ui(
                        "Parallel media downloads per run.",
                        "تنزيلات وسائط متوازية لكل تشغيل.",
                    ),
                },
                {
                    "label": ui("Max document size", "أقصى حجم للملف"),
                    "value": f"{SS.MAX_DOCUMENT_MB} MB",
                    "hint": ui(
                        "Maximum allowed document size.",
                        "أقصى حجم مسموح للمستند.",
                    ),
                },
                {
                    "label": ui("Max image size", "أقصى حجم للصورة"),
                    "value": f"{SS.MAX_IMAGE_MB} MB",
                    "hint": ui(
                        "Maximum allowed image size.",
                        "أقصى حجم مسموح للصورة.",
                    ),
                },
                {
                    "label": ui(
                        "Automatic schedules enabled", "الجدولة التلقائية مفعلة"
                    ),
                    "value": bool_no
                    if bool(getattr(settings, "SCRAPING_MANUAL_ONLY", True))
                    else bool_yes,
                    "hint": ui(
                        "If disabled, runs are manual-only.",
                        "عند تعطيلها تصبح التشغيلات يدوية فقط.",
                    ),
                },
            ],
        },
    ]

    has_active_sources = source_stats["active"] > 0
    context = {
        "page": "scraping",
        "category_key": category_key,
        "category_name": category_name,
        "category_active_tab": "settings",
        "category_global_status": "ok" if has_active_sources else "warn",
        "category_global_status_label": (
            ui("Global status: OK", "الحالة العامة: جيد")
            if has_active_sources
            else ui(
                "Global status: No active sources", "الحالة العامة: لا توجد مصادر نشطة"
            )
        ),
        "source_stats": source_stats,
        "schedule_tier_labels": schedule_tier_labels,
        "schedule_tier_counts": schedule_tier_counts,
        "schedule_tier_rows": schedule_tier_rows,
        "validation_counts": validation_counts,
        "source_rows": source_rows,
        "query_rows": query_rows,
        "active_query_count": active_query_count,
        "settings_sections": settings_sections,
        "settings_update_source_url_template": reverse(
            "scraping:update_source_settings",
            kwargs={"source_id": uuid.UUID("00000000-0000-0000-0000-000000000000")},
        ),
        "settings_toggle_query_url_template": reverse(
            "scraping:toggle_prompt_api",
            kwargs={"query_id": 0},
        ),
        "settings_add_query_url": reverse("scraping:add_prompt_api"),
        **_scraping_shell_context(request, active_page="settings"),
    }
    return render(request, "scraping/settings.html", context)


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def mark_notifications_read(request):
    """Mark all scraping notifications as read from the topbar dropdown."""
    _log_scraping_action(request)
    updated_count = ScrapingNotification.objects.filter(is_read=False).update(
        is_read=True
    )
    return JsonResponse(
        {
            "success": True,
            "updated": int(updated_count),
            "unread_count": 0,
        }
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


def _collect_quick_stats_payload() -> dict:
    today = timezone.localdate()
    reviewed_today_approved = 0
    reviewed_today_rejected = 0

    for cfg in _scraping_result_category_map().values():
        model_cls = cfg.get("model")
        status_field = cfg.get("status_field")
        if not model_cls or not status_field:
            continue

        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }

        approved_qs = model_cls.objects.filter(**{status_field: "approved"})
        rejected_qs = model_cls.objects.filter(**{status_field: "rejected"})

        date_field = None
        for candidate in ("approval_date", "updated_at", cfg.get("date_field")):
            if candidate and candidate in field_names:
                date_field = candidate
                break

        if date_field:
            approved_qs = approved_qs.filter(**{f"{date_field}__date": today})
            rejected_qs = rejected_qs.filter(**{f"{date_field}__date": today})

        reviewed_today_approved += approved_qs.count()
        reviewed_today_rejected += rejected_qs.count()

    meta_agg = ScrapedItemMeta.objects.aggregate(
        avg_confidence=Avg("relevance_score"),
        total=Count("id"),
        translated=Count("id", filter=Q(translation_status="translated")),
    )
    total_items = int(meta_agg.get("total") or 0)
    translated_items = int(meta_agg.get("translated") or 0)
    avg_confidence = float(meta_agg.get("avg_confidence") or 0.0)
    translation_ok_pct = (
        round((translated_items / total_items) * 100.0, 1) if total_items else 0.0
    )

    return {
        "today_approved": reviewed_today_approved,
        "today_rejected": reviewed_today_rejected,
        "avg_confidence": round(avg_confidence, 1),
        "translation_ok_pct": translation_ok_pct,
        "translation_total": total_items,
        "translation_translated": translated_items,
    }


def _scraping_result_category_map():
    def _resolve_dynamic_model(model_candidates: list[tuple[str, str]]):
        for app_label, model_name in model_candidates:
            try:
                model_cls = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            if model_cls is not None:
                return model_cls
        return None

    def _first_existing_field(model_cls, *candidates):
        if model_cls is None:
            return None
        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        for candidate in candidates:
            if candidate in field_names:
                return candidate
        return None

    category_map = {
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
        "news": {
            "label": "News",
            "model": Post,
            "title_field": "title",
            "description_field": "content",
            "source_field": "source_url",
            "date_field": "created_at",
            "status_field": "approval_status",
            "entity_field": "entities",
            "confidence_field": "relevance_score",
        },
    }

    opportunity_model = _resolve_dynamic_model(
        [
            ("pages", "Opportunity"),
            ("events", "Opportunity"),
            ("resources", "Opportunity"),
        ]
    )
    if opportunity_model is not None:
        title_field = _first_existing_field(
            opportunity_model,
            "title",
            "title_en",
            "job_title",
            "name",
        )
        description_field = _first_existing_field(
            opportunity_model,
            "description",
            "description_en",
            "summary",
            "content",
        )
        source_field = _first_existing_field(
            opportunity_model,
            "source_url",
            "url",
            "access_link",
            "application_url",
            "contact",
        )
        date_field = _first_existing_field(
            opportunity_model,
            "created_at",
            "creation_date",
            "updated_at",
        )
        status_field = _first_existing_field(
            opportunity_model,
            "approval_status",
            "status",
        )

        if (
            title_field
            and description_field
            and source_field
            and date_field
            and status_field
        ):
            category_map["opportunities"] = {
                "label": "Opportunities",
                "model": opportunity_model,
                "title_field": title_field,
                "description_field": description_field,
                "source_field": source_field,
                "date_field": date_field,
                "status_field": status_field,
                "entity_field": _first_existing_field(
                    opportunity_model,
                    "skills",
                    "keywords",
                    "entities",
                ),
                "location_field": _first_existing_field(
                    opportunity_model,
                    "location",
                    "city",
                ),
                "confidence_field": _first_existing_field(
                    opportunity_model,
                    "relevance_score",
                ),
            }

    corpus_model = _resolve_dynamic_model(
        [
            ("events", "Corpus"),
            ("resources", "Corpus"),
            ("corpus", "Corpus"),
        ]
    )
    if corpus_model is not None:
        title_field = _first_existing_field(
            corpus_model,
            "title",
            "title_en",
            "dataset_name",
            "name",
        )
        description_field = _first_existing_field(
            corpus_model,
            "description",
            "description_en",
            "summary",
            "content",
        )
        source_field = _first_existing_field(
            corpus_model,
            "source_url",
            "access_link",
            "url",
            "download_url",
            "paper_url",
        )
        date_field = _first_existing_field(
            corpus_model,
            "creation_date",
            "created_at",
            "updated_at",
        )
        status_field = _first_existing_field(
            corpus_model,
            "approval_status",
            "status",
        )

        if (
            title_field
            and description_field
            and source_field
            and date_field
            and status_field
        ):
            category_map["corpus"] = {
                "label": "Corpus",
                "model": corpus_model,
                "title_field": title_field,
                "description_field": description_field,
                "source_field": source_field,
                "date_field": date_field,
                "status_field": status_field,
                "entity_field": _first_existing_field(
                    corpus_model,
                    "keywords",
                    "language_variants",
                    "entities",
                ),
                "confidence_field": _first_existing_field(
                    corpus_model,
                    "relevance_score",
                ),
            }

    return category_map


def _scraping_pending_queue_count(category: str | None = None) -> int:
    total_pending = 0
    category_map = _scraping_result_category_map()
    if category:
        cfg = category_map.get(str(category).strip().lower())
        iterable_cfgs = [cfg] if cfg else []
    else:
        iterable_cfgs = list(category_map.values())

    for cfg in iterable_cfgs:
        if not cfg:
            continue
        model_cls = cfg.get("model")
        status_field = cfg.get("status_field")
        source_field = cfg.get("source_field")
        if model_cls is None or not status_field or not source_field:
            continue

        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        if status_field not in field_names or source_field not in field_names:
            continue

        category_qs = model_cls.objects.exclude(
            **{f"{source_field}__isnull": True}
        ).exclude(**{source_field: ""})
        total_pending += category_qs.filter(**{status_field: "pending"}).count()

    return int(total_pending)


def _scraping_nav_categories() -> list[dict[str, str]]:
    categories: list[dict[str, str]] = []
    for key in SCRAPING_NAV_CATEGORY_KEYS:
        meta = (CATEGORY_META.get(key, {}) or {}).copy()
        categories.append(
            {
                "key": key,
                "label": str(_(meta.get("label", key.title()))),
            }
        )
    return categories


def _resolve_scraping_nav_category(request) -> str:
    resolver_category = ""
    if request.resolver_match is not None:
        resolver_category = (
            str((request.resolver_match.kwargs or {}).get("category") or "")
            .strip()
            .lower()
        )

    current_category = (
        str(
            getattr(request, "_scraping_category", "")
            or resolver_category
            or request.GET.get("category")
            or "events"
        )
        .strip()
        .lower()
    )

    if current_category not in SCRAPING_NAV_CATEGORY_KEYS:
        current_category = "events"
    return current_category


def _resolve_scraping_selected_category(request) -> str:
    if request.resolver_match is None:
        return ""

    resolver_category = (
        str((request.resolver_match.kwargs or {}).get("category") or "").strip().lower()
    )
    if resolver_category in SCRAPING_NAV_CATEGORY_KEYS:
        return resolver_category
    return ""


def _set_category_request_context(request, category: str) -> str:
    category_key = str(category or "").strip().lower()
    if category_key not in SCRAPING_NAV_CATEGORY_KEYS:
        raise Http404(_("Unknown scraping category."))

    request._scraping_category = category_key
    query_params = request.GET.copy()
    query_params["category"] = category_key
    request.GET = query_params
    return category_key


def _build_scraping_breadcrumbs(request) -> list[dict[str, str]]:
    language_code = str(getattr(request, "LANGUAGE_CODE", "") or "").lower()
    is_rtl = language_code.startswith("ar")

    def crumb(en_text: str, ar_text: str) -> str:
        return ar_text if is_rtl else str(_(en_text))

    selected_category = _resolve_scraping_selected_category(request)
    current_category = _resolve_scraping_nav_category(request)
    category_for_links = selected_category or current_category
    category_dashboard_url = reverse(
        "scraping:category_dashboard",
        kwargs={"category": category_for_links},
    )
    root_dashboard_url = reverse("scraping:dashboard")
    dashboard_url = category_dashboard_url if selected_category else root_dashboard_url

    breadcrumbs: list[dict[str, str]] = [
        {
            "label": crumb("Scraping", "الاستخراج"),
            "url": dashboard_url,
        }
    ]

    url_name = ""
    kwargs = {}
    if request.resolver_match is not None:
        url_name = str(request.resolver_match.url_name or "")
        kwargs = request.resolver_match.kwargs or {}

    if url_name == "category_dashboard" or url_name in {
        "dashboard",
        "scraping_dashboard",
    }:
        breadcrumbs.append({"label": crumb("Hub", "المركز"), "url": ""})
    elif url_name == "category_results" or url_name in {"results", "scraping_results"}:
        breadcrumbs.append(
            {"label": crumb("Pending Queue", "قائمة المراجعة"), "url": ""}
        )
    elif url_name in {"result_detail", "scraping_result_detail"}:
        breadcrumbs.append(
            {
                "label": crumb("Pending Queue", "قائمة المراجعة"),
                "url": reverse("scraping:results"),
            }
        )
        raw_item_id = str(kwargs.get("item_id") or "").strip()
        short_item_id = raw_item_id
        if "-" in short_item_id:
            short_item_id = short_item_id.split("-", 1)[0]
        if len(short_item_id) > 8:
            short_item_id = short_item_id[:8]
        item_label = crumb("Item", "عنصر")
        if short_item_id:
            item_label = f"{item_label} #{short_item_id}"
        breadcrumbs.append({"label": item_label, "url": ""})
    elif url_name == "category_analytics" or url_name in {
        "scraping_analytics",
        "analytics",
    }:
        breadcrumbs.append({"label": crumb("Analytics", "التحليلات"), "url": ""})
    elif url_name == "category_sources" or url_name in {"scraping_sources", "sources"}:
        breadcrumbs.append({"label": crumb("Sources", "المصادر"), "url": ""})
    elif url_name == "category_settings" or url_name in {
        "settings",
        "scraping_settings",
    }:
        breadcrumbs.append({"label": crumb("Settings", "الإعدادات"), "url": ""})

    return breadcrumbs


def _scraping_shell_context(request, *, active_page: str) -> dict:
    notification_rows = list(
        ScrapingNotification.objects.select_related("run").order_by("-created_at")[:8]
    )
    unread_count = int(ScrapingNotification.objects.filter(is_read=False).count())

    admin_name = ""
    admin_avatar_url = ""
    admin_initials = "A"
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        name_candidate = ""
        if hasattr(request.user, "get_full_name_display") and callable(
            request.user.get_full_name_display
        ):
            name_candidate = str(request.user.get_full_name_display() or "").strip()
        if not name_candidate:
            name_candidate = str(request.user.get_full_name() or "").strip()
        if "@" in name_candidate:
            name_candidate = ""

        if not name_candidate:
            username_candidate = str(request.user.get_username() or "").strip()
            if username_candidate:
                name_candidate = username_candidate.split("@", 1)[0].strip()
        if not name_candidate:
            name_candidate = str(_("Administrator"))
        admin_name = name_candidate

        avatar_obj = getattr(request.user, "avatar", None)
        if avatar_obj:
            try:
                admin_avatar_url = str(avatar_obj.url or "")
            except Exception:
                admin_avatar_url = ""

        if hasattr(request.user, "get_initials") and callable(
            request.user.get_initials
        ):
            initials_candidate = str(request.user.get_initials() or "").strip()
            if initials_candidate:
                admin_initials = initials_candidate[:2].upper()
        elif admin_name:
            admin_initials = admin_name[:1].upper()

    nav_categories = _scraping_nav_categories()
    current_category = _resolve_scraping_nav_category(request)
    selected_category = _resolve_scraping_selected_category(request)
    pending_count = _scraping_pending_queue_count(selected_category or None)
    language_code = str(getattr(request, "LANGUAGE_CODE", "") or "").lower()
    is_rtl = language_code.startswith("ar")

    return {
        "scraping_active_page": active_page,
        "scraping_is_rtl": is_rtl,
        "scraping_nav_categories": nav_categories,
        "scraping_current_category": current_category,
        "scraping_selected_category": selected_category,
        "scraping_pending_count": pending_count,
        "scraping_notifications": notification_rows,
        "scraping_unread_count": unread_count,
        "scraping_admin_name": admin_name,
        "scraping_admin_avatar_url": admin_avatar_url,
        "scraping_admin_initials": admin_initials,
        "scraping_breadcrumbs": _build_scraping_breadcrumbs(request),
        "scraping_mark_notifications_read_url": reverse(
            "scraping:mark_notifications_read"
        ),
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


REJECT_REASON_LABELS = {
    "irrelevant": "Irrelevant to Arabic NLP",
    "poor_arabic": "Poor Arabic translation",
    "duplicate": "Duplicate content",
    "unreliable_source": "Unreliable source",
    "outdated": "Outdated information",
    "low_quality": "Low quality content",
    "other": "Other",
}


def _normalize_reject_reason_code(raw_reason: str) -> str:
    reason_code = str(raw_reason or "").strip().lower()
    if reason_code == "poor_translation":
        reason_code = "poor_arabic"
    return reason_code if reason_code in REJECT_REASON_LABELS else "other"


def _build_rejection_reason_text(reason_code: str, reject_notes: str) -> str:
    label = REJECT_REASON_LABELS.get(reason_code, REJECT_REASON_LABELS["other"])
    notes = str(reject_notes or "").strip()
    if notes:
        return f"{label}: {notes}"
    return label


def _record_rejected_item_audit(
    obj,
    cfg,
    *,
    category: str,
    reason_code: str,
    reason_text: str,
    reject_notes: str,
    rejected_by=None,
) -> None:
    title_candidates = [
        f"{cfg.get('title_field', 'title')}_en",
        cfg.get("title_field", "title"),
        "title",
        "name",
        "job_title",
        "dataset_name",
    ]
    model_field_names = {
        field.name
        for field in obj._meta.get_fields()
        if getattr(field, "concrete", False)
    }
    title_value = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=title_candidates,
        default=str(obj),
    )

    rejected_model_field_names = {
        field.name
        for field in RejectedItem._meta.get_fields()
        if getattr(field, "concrete", False)
    }
    record_kwargs = {
        "category": category,
        "title": title_value[:300],
        "reason_for_rejection": reason_text,
    }
    if "reason" in rejected_model_field_names:
        record_kwargs["reason"] = reason_code
    if "note" in rejected_model_field_names:
        record_kwargs["note"] = str(reject_notes or "")
    if "notes" in rejected_model_field_names:
        record_kwargs["notes"] = str(reject_notes or "")
    if "rejected_by" in rejected_model_field_names and rejected_by is not None:
        record_kwargs["rejected_by"] = rejected_by
    if "rejected_at" in rejected_model_field_names:
        record_kwargs["rejected_at"] = timezone.now()
    if "content_type" in rejected_model_field_names:
        record_kwargs["content_type"] = ContentType.objects.get_for_model(
            obj,
            for_concrete_model=False,
        )
    if "object_id" in rejected_model_field_names:
        record_kwargs["object_id"] = str(obj.pk)

    RejectedItem.objects.create(**record_kwargs)


def _apply_scraping_item_action(
    obj,
    cfg,
    *,
    action: str,
    category: str,
    reject_reason: str = "other",
    reject_notes: str = "",
    user=None,
) -> int:
    normalized_action = str(action or "").strip().lower()

    if normalized_action in {"validate", "approve"}:
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

    if normalized_action == "reject":
        model_field_names = {f.name for f in obj._meta.get_fields()}
        status_field = cfg["status_field"]
        setattr(obj, status_field, "rejected")

        reason_code = _normalize_reject_reason_code(reject_reason)
        reason_text = _build_rejection_reason_text(reason_code, reject_notes)

        update_fields = [status_field]
        if "is_approved" in model_field_names:
            obj.is_approved = False
            update_fields.append("is_approved")
        if "rejection_reason" in model_field_names:
            obj.rejection_reason = reason_code
            update_fields.append("rejection_reason")
        if "rejection_note" in model_field_names:
            obj.rejection_note = str(reject_notes or "")
            update_fields.append("rejection_note")
        if "rejection_notes" in model_field_names:
            obj.rejection_notes = str(reject_notes or "")
            update_fields.append("rejection_notes")
        if "rejected_at" in model_field_names:
            obj.rejected_at = timezone.now()
            update_fields.append("rejected_at")
        if "rejected_by" in model_field_names and user is not None:
            obj.rejected_by = user
            update_fields.append("rejected_by")
        if "approval_date" in model_field_names:
            obj.approval_date = timezone.now()
            update_fields.append("approval_date")

        obj.save(update_fields=update_fields)

        try:
            _record_rejected_item_audit(
                obj,
                cfg,
                category=category,
                reason_code=reason_code,
                reason_text=reason_text,
                reject_notes=reject_notes,
                rejected_by=user,
            )
        except Exception as exc:
            logger.error("Failed to create RejectedItem record: %s", exc)

        return 1

    if normalized_action == "delete":
        deleted_count, _ = obj.delete()
        return int(deleted_count)

    return 0


RESULTS_FILTER_PARAM_KEYS = (
    "source",
    "confidence",
    "translation",
    "date_range",
    "date_from",
    "date_to",
    "per_page",
    "page",
)


def _parse_date_param(raw_value) -> date | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_compare_text(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _infer_translation_state(
    title_en: str,
    title_ar: str,
    raw_translation_status: str,
) -> str:
    title_en_norm = _normalize_compare_text(title_en)
    title_ar_norm = _normalize_compare_text(title_ar)

    if not title_ar_norm:
        return "missing"
    if title_en_norm and title_ar_norm == title_en_norm:
        return "copied"

    status = str(raw_translation_status or "").strip().lower()
    if status == "translated":
        return "translated"
    if status in {"copied", "partial", "failed"}:
        return "copied"
    if status in {"missing", "pending"}:
        return "missing"
    return "translated"


def _confidence_band(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score > 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def _confidence_filter_match(score: float | None, confidence_filter: str) -> bool:
    if confidence_filter == "any":
        return True

    if confidence_filter == "unknown":
        return score is None

    if score is None:
        return False

    if confidence_filter == "high":
        return score > 80
    if confidence_filter == "medium":
        return 60 <= score <= 80
    if confidence_filter == "low":
        return score < 60
    return True


def _translation_filter_match(translation_state: str, translation_filter: str) -> bool:
    if translation_filter == "any":
        return True
    return translation_state == translation_filter


def _extract_results_filters(raw_params) -> dict:
    category = (raw_params.get("category") or "all").strip().lower()
    if not category:
        category = "all"

    confidence = (raw_params.get("confidence") or "any").strip().lower()
    if confidence not in {"any", "high", "medium", "low", "unknown"}:
        confidence = "any"

    translation = (raw_params.get("translation") or "any").strip().lower()
    if translation not in {"any", "translated", "copied", "missing"}:
        translation = "any"

    date_range = (raw_params.get("date_range") or "any").strip().lower()
    if date_range not in {"any", "today", "last7", "month", "custom"}:
        date_range = "any"

    per_page = str(raw_params.get("per_page") or "25").strip()
    if per_page not in {"25", "50", "100"}:
        per_page = "25"

    page = str(raw_params.get("page") or "1").strip() or "1"

    return {
        "category": category,
        "q": (raw_params.get("q") or "").strip(),
        "run_id": (raw_params.get("run_id") or "").strip(),
        "source": (raw_params.get("source") or "any").strip(),
        "confidence": confidence,
        "translation": translation,
        "date_range": date_range,
        "date_from": _parse_date_param(raw_params.get("date_from")),
        "date_to": _parse_date_param(raw_params.get("date_to")),
        "date_from_raw": (raw_params.get("date_from") or "").strip(),
        "date_to_raw": (raw_params.get("date_to") or "").strip(),
        "per_page": per_page,
        "page": page,
    }


def _results_redirect_url(
    category: str = "",
    query: str = "",
    run_id: str | None = None,
    extra_params: dict | None = None,
) -> str:
    params = {}
    if category and category != "all":
        params["category"] = category
    if query:
        params["q"] = query
    if run_id:
        params["run_id"] = run_id

    if extra_params:
        for key in RESULTS_FILTER_PARAM_KEYS:
            value = extra_params.get(key)
            if value in {None, "", "any"}:
                continue
            params[key] = value

    url = reverse("scraping:scraping_results")
    if params:
        return f"{url}?{urlencode(params)}"
    return url


def _safe_next_url(request, raw_next_url: str | None) -> str:
    candidate = str(raw_next_url or "").strip()
    if not candidate:
        return ""
    if url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return ""


def _build_detail_query_params(filters: dict, *, item_category: str) -> dict:
    params = {}

    category = (filters.get("category") or "all").strip().lower()
    if category:
        params["category"] = category

    query = (filters.get("q") or "").strip()
    if query:
        params["q"] = query

    run_id = (filters.get("run_id") or "").strip()
    if run_id:
        params["run_id"] = run_id

    source = (filters.get("source") or "any").strip()
    if source and source != "any":
        params["source"] = source

    confidence = (filters.get("confidence") or "any").strip().lower()
    if confidence and confidence != "any":
        params["confidence"] = confidence

    translation = (filters.get("translation") or "any").strip().lower()
    if translation and translation != "any":
        params["translation"] = translation

    date_range = (filters.get("date_range") or "any").strip().lower()
    if date_range and date_range != "any":
        params["date_range"] = date_range

    date_from = (filters.get("date_from_raw") or "").strip()
    if date_from:
        params["date_from"] = date_from

    date_to = (filters.get("date_to_raw") or "").strip()
    if date_to:
        params["date_to"] = date_to

    per_page = str(filters.get("per_page") or "25").strip()
    if per_page:
        params["per_page"] = per_page

    page = str(filters.get("page") or "1").strip()
    if page:
        params["page"] = page

    if item_category:
        params["item_category"] = item_category

    return params


def _build_result_detail_url(item_id, *, item_category: str, filters: dict) -> str:
    base_url = reverse("scraping:scraping_result_detail", args=[item_id])
    params = _build_detail_query_params(filters, item_category=item_category)
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_available_text(
    obj,
    *,
    model_field_names: set[str],
    candidates: list[str],
    default: str = "",
) -> str:
    for candidate in candidates:
        if not candidate or candidate not in model_field_names:
            continue
        value = _safe_text(getattr(obj, candidate, ""))
        if value:
            return value
    return _safe_text(default)


def _translation_state_for_pair(
    *,
    source_text: str,
    target_text: str,
    raw_translation_status: str,
) -> str:
    source_norm = _normalize_compare_text(source_text)
    target_norm = _normalize_compare_text(target_text)

    if not target_norm:
        return "missing"
    if source_norm and source_norm == target_norm:
        return "copied"

    status = str(raw_translation_status or "").strip().lower()
    if status in {"copied"}:
        return "copied"
    if status in {"missing"}:
        return "missing"
    if status in {"translated"}:
        return "translated"

    # If Arabic text is present and not identical to the source, treat it as translated
    # even when upstream status tracking is stale (e.g. still "pending").
    return "translated"


def _text_quality_score(text_value: str, *, long_form: bool = False) -> int:
    text = _safe_text(text_value)
    if not text:
        return 0
    if not long_form:
        return 100

    text_length = len(text)
    if text_length >= 180:
        return 100
    if text_length >= 80:
        return 80
    if text_length >= 30:
        return 60
    return 40


def _breakdown_state_for_score(score: int, *, translation_state: str = "") -> str:
    if translation_state == "copied":
        return "copied"
    if score <= 0:
        return "missing"
    if score >= 80:
        return "good"
    if score >= 60:
        return "partial"
    return "missing"


def _to_arabic_digits(raw_value: str) -> str:
    text = _safe_text(raw_value)
    if not text:
        return ""

    digit_map = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    return text.translate(digit_map)


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


def _build_scraping_results_dataset(
    category_map: dict,
    *,
    selected_category: str,
    selected_run,
    query: str,
    selected_source: str,
    confidence_filter: str,
    translation_filter: str,
    date_range: str,
    date_from: date | None,
    date_to: date | None,
    selected_run_id: str,
) -> dict:
    if selected_run:
        active_categories = [selected_run.category]
    elif selected_category == "all":
        active_categories = list(category_map.keys())
    else:
        active_categories = [selected_category]

    run_window_start = selected_run.started_at if selected_run else None
    run_window_end = None
    if selected_run:
        run_window_end = (selected_run.completed_at or timezone.now()) + timedelta(
            minutes=5
        )

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

    base_rows = []
    by_category_item_ids = defaultdict(list)
    by_category_titles = defaultdict(list)

    today_date = timezone.localdate()
    month_start = today_date.replace(day=1)
    last7_start = today_date - timedelta(days=6)

    for cat_key in active_categories:
        if cat_key not in category_map:
            continue

        cfg = category_map[cat_key]
        model = cfg["model"]
        title_field = cfg["title_field"]
        description_field = cfg["description_field"]
        source_field = cfg["source_field"]
        date_field = cfg["date_field"]
        status_field = cfg["status_field"]

        model_field_names = {
            field.name
            for field in model._meta.get_fields()
            if getattr(field, "concrete", False)
        }

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
            queryset = queryset.filter(
                Q(**{f"{title_field}__icontains": query})
                | Q(**{f"{source_field}__icontains": query})
            )

        if date_range == "today":
            queryset = queryset.filter(**{f"{date_field}__date": today_date})
        elif date_range == "last7":
            queryset = queryset.filter(**{f"{date_field}__date__gte": last7_start})
        elif date_range == "month":
            queryset = queryset.filter(**{f"{date_field}__date__gte": month_start})
        elif date_range == "custom":
            if date_from is not None:
                queryset = queryset.filter(**{f"{date_field}__date__gte": date_from})
            if date_to is not None:
                queryset = queryset.filter(**{f"{date_field}__date__lte": date_to})

        queryset = queryset.order_by(f"-{date_field}")

        for obj in queryset:
            title_en_candidates = [
                f"{title_field}_en",
                "title_en",
                "name_en",
                "job_title_en",
                title_field,
                "title",
                "name",
                "job_title",
                "dataset_name",
            ]
            title_ar_candidates = [
                f"{title_field}_ar",
                "title_ar",
                "name_ar",
                "job_title_ar",
                "dataset_name_ar",
            ]

            title_en = ""
            for candidate in title_en_candidates:
                if candidate not in model_field_names:
                    continue
                value = str(getattr(obj, candidate, "") or "").strip()
                if value:
                    title_en = value
                    break
            if not title_en:
                title_en = str(getattr(obj, title_field, "") or "").strip() or str(obj)

            title_ar = ""
            for candidate in title_ar_candidates:
                if candidate not in model_field_names:
                    continue
                value = str(getattr(obj, candidate, "") or "").strip()
                if value:
                    title_ar = value
                    break

            description_value = str(getattr(obj, description_field, "") or "").strip()
            source_value = str(getattr(obj, source_field, "") or "").strip()
            source_domain = (urlparse(source_value).netloc or "").lower()
            date_value = getattr(obj, date_field, None)
            status_value = getattr(obj, status_field, "pending") or "pending"

            raw_confidence = None
            confidence_field = cfg.get("confidence_field")
            if confidence_field and confidence_field in model_field_names:
                raw_confidence = getattr(obj, confidence_field, None)

            raw_translation_status = ""
            if "translation_status" in model_field_names:
                raw_translation_status = str(
                    getattr(obj, "translation_status", "") or ""
                ).strip()

            item_id_str = str(obj.pk)
            by_category_item_ids[cat_key].append(item_id_str)
            if title_en:
                by_category_titles[cat_key].append(title_en)

            # Populate all available model fields so the confidence
            # calculator has real data to score (not just title/description).
            row_data = {
                "selection_key": f"{cat_key}:{item_id_str}",
                "item_id": item_id_str,
                "title": title_en,
                "title_en": title_en,
                "title_ar": title_ar,
                "category": cat_key,
                "category_label": cfg["label"],
                "source_url": source_value,
                "source_domain": source_domain,
                "scraped_date": date_value,
                "description": description_value,
                "description_en": description_value,
                "confidence_score": raw_confidence,
                "raw_translation_status": raw_translation_status,
                "status": _result_status_label(status_value),
                "status_badge": _result_status_badge(status_value),
                "detail_url": reverse(
                    "scraping:scraping_result_detail", args=[obj.pk]
                )
                + f"?category={cat_key}"
                + (f"&run_id={selected_run_id}" if selected_run_id else ""),
                "run_id": selected_run_id,
            }
            # Pull in extra model fields that the confidence calculator
            # checks (url, location, start_date, job_title, dataset_name, etc.)
            _extra_fields = (
                "url", "access_link", "location", "location_en",
                "start_date", "end_date", "published_date",
                "job_title", "institution_name", "deadline",
                "dataset_name", "download_url", "paper_url",
                "platform", "level", "price",
            )
            for _ef in _extra_fields:
                if _ef in model_field_names and _ef not in row_data:
                    _val = getattr(obj, _ef, None)
                    if _val is not None:
                        row_data[_ef] = _val
            base_rows.append(row_data)

    meta_by_item = defaultdict(dict)
    meta_by_title = defaultdict(dict)
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
            if meta.item_id and meta.item_id not in meta_by_item[cat_key]:
                meta_by_item[cat_key][meta.item_id] = meta
            if meta.item_title and meta.item_title not in meta_by_title[cat_key]:
                meta_by_title[cat_key][meta.item_title] = meta

    source_options_set = set()
    rows = []
    for row in base_rows:
        cat_key = row["category"]
        meta = meta_by_item[cat_key].get(row["item_id"]) or meta_by_title[cat_key].get(
            row["title_en"]
        )

        score = row.get("confidence_score")
        if meta and meta.relevance_score is not None:
            score = float(meta.relevance_score)

        # Only compute a live score if no stored confidence is available.
        # The stored confidence_score from the model is the authoritative value.
        if score is None or score <= 0:
            live_score = compute_relevance_score(category=cat_key, item_data=row)
            if live_score > 0:
                score = live_score

        if score is not None:
            score = round(float(score), 2)

        raw_translation_status = row["raw_translation_status"]
        if not raw_translation_status and meta:
            raw_translation_status = str(meta.translation_status or "")

        translation_state = _infer_translation_state(
            row["title_en"],
            row["title_ar"],
            raw_translation_status,
        )
        if row["source_domain"]:
            source_options_set.add(row["source_domain"])

        if selected_source and selected_source != "any":
            if selected_source.lower() not in (row["source_domain"] or ""):
                continue

        if not _confidence_filter_match(score, confidence_filter):
            continue

        if not _translation_filter_match(translation_state, translation_filter):
            continue

        title_en_ok = bool(str(row["title_en"]).strip())
        title_ar_icon = (
            "✅"
            if translation_state == "translated"
            else ("⚠️" if translation_state == "copied" else "❌")
        )
        description_icon = "✅" if bool(str(row["description"]).strip()) else "❌"
        date_icon = "✅" if row["scraped_date"] else "❌"

        row["confidence_score"] = score
        row["confidence_band"] = _confidence_band(score)
        row["translation_state"] = translation_state
        row["is_ar_copied"] = translation_state == "copied"
        row["is_ar_missing"] = translation_state == "missing"
        row["confidence_breakdown"] = (
            f"Title EN {'✅' if title_en_ok else '❌'} "
            f"Title AR {title_ar_icon} "
            f"Description {description_icon} "
            f"Date {date_icon}"
        )
        rows.append(row)

    rows.sort(
        key=lambda record: (
            1 if record["scraped_date"] is not None else 0,
            str(record["scraped_date"] or ""),
        ),
        reverse=True,
    )

    filtered_category_counts = defaultdict(int)
    filtered_low_confidence_count = 0
    for row in rows:
        filtered_category_counts[row["category"]] += 1
        if row["confidence_score"] is not None and row["confidence_score"] < 60:
            filtered_low_confidence_count += 1

    return {
        "rows": rows,
        "pending_counts": pending_counts,
        "source_options": sorted(source_options_set),
        "active_categories": active_categories,
        "filtered_total": len(rows),
        "filtered_category_counts": dict(filtered_category_counts),
        "filtered_low_confidence_count": filtered_low_confidence_count,
    }


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_result_validate(request, item_id):
    """POST /scraping/results/validate/<item_id>/."""
    _log_scraping_action(request)
    filters = _extract_results_filters(request.POST)
    category_hint = filters["category"]
    query = filters["q"]
    run_id = filters["run_id"]

    category_for_lookup = None if category_hint in {"", "all"} else category_hint
    cat_key, cfg, obj = _resolve_scraping_item(item_id, category_for_lookup)
    next_item_url = _safe_next_url(request, request.POST.get("next_item_url"))

    if not obj or not cfg or not cat_key:
        messages.error(request, "Scraped item not found.")
        return redirect(
            _results_redirect_url(
                category_hint,
                query,
                run_id=run_id,
                extra_params=filters,
            )
        )

    affected = _apply_scraping_item_action(
        obj,
        cfg,
        action="validate",
        category=cat_key,
        user=request.user,
    )
    if affected:
        messages.success(request, "Item published successfully.")
        if next_item_url:
            return redirect(next_item_url)
    else:
        messages.warning(request, "No item was published.")

    return redirect(
        _results_redirect_url(
            category_hint,
            query,
            run_id=run_id,
            extra_params=filters,
        )
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_result_delete(request, item_id):
    """POST /scraping/results/delete/<item_id>/."""
    _log_scraping_action(request)
    filters = _extract_results_filters(request.POST)
    category_hint = filters["category"]
    query = filters["q"]
    run_id = filters["run_id"]

    category_for_lookup = None if category_hint in {"", "all"} else category_hint
    cat_key, cfg, obj = _resolve_scraping_item(item_id, category_for_lookup)
    next_item_url = _safe_next_url(request, request.POST.get("next_item_url"))

    if not obj or not cfg or not cat_key:
        messages.error(request, "Scraped item not found.")
        return redirect(
            _results_redirect_url(
                category_hint,
                query,
                run_id=run_id,
                extra_params=filters,
            )
        )

    affected = _apply_scraping_item_action(
        obj,
        cfg,
        action="delete",
        category=cat_key,
        user=request.user,
    )
    if affected:
        messages.success(request, "Item deleted successfully.")
        if next_item_url:
            return redirect(next_item_url)
    else:
        messages.warning(request, "No item was deleted.")

    return redirect(
        _results_redirect_url(
            category_hint,
            query,
            run_id=run_id,
            extra_params=filters,
        )
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=120, period_seconds=60, scope="action")
def translate_field_api(request):
    """POST /scraping/api/translate-field/ for on-demand Arabic translation."""
    _log_scraping_action(request)

    content_type_error = _require_json_content_type(request)
    if content_type_error:
        return content_type_error

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    item_id = _safe_text(payload.get("item_id"))
    field_name = _safe_text(payload.get("field_name"))
    source_text = _safe_text(payload.get("source_text"))
    category_hint = _safe_text(payload.get("category")).lower()

    if not item_id:
        return JsonResponse({"error": "item_id is required"}, status=400)
    if not field_name:
        return JsonResponse({"error": "field_name is required"}, status=400)
    if not source_text:
        return JsonResponse({"error": "source_text is required"}, status=400)

    resolved_category = None if category_hint in {"", "all"} else category_hint
    cat_key, _cfg, obj = _resolve_scraping_item(item_id, resolved_category)
    if obj is None or not cat_key:
        return JsonResponse({"error": "Scraped item not found"}, status=404)

    field_type_hint = _safe_text(payload.get("field_type")).lower()
    if field_type_hint not in {"title", "description", "short_description", "tags"}:
        if "title" in field_name:
            field_type_hint = "title"
        elif "description" in field_name or "content" in field_name:
            field_type_hint = "description"
        else:
            field_type_hint = "title"

    translator = ArabicTranslator()
    translated_text = translator.translate_field(source_text, field_type_hint)
    if not translated_text:
        return JsonResponse(
            {
                "error": "translation_failed",
                "message": "Unable to translate field right now.",
            },
            status=502,
        )

    model_used = ""
    if translator.primary_client and translator.primary_client.is_configured:
        model_used = _safe_text(translator.primary_client.model)
    elif translator.fallback_client and translator.fallback_client.is_configured:
        model_used = _safe_text(translator.fallback_client.model)
    if not model_used:
        model_used = "unknown"

    estimated_confidence = 0.9 if len(translated_text) >= 20 else 0.75

    return JsonResponse(
        {
            "translated_text": translated_text,
            "model_used": model_used,
            "confidence": estimated_confidence,
            "category": cat_key,
            "field_name": field_name,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=120, period_seconds=60, scope="action")
def save_draft_api(request, item_id):
    """POST /scraping/api/save-draft/<item_id>/ for inline moderation edits."""
    _log_scraping_action(request)

    content_type_error = _require_json_content_type(request)
    if content_type_error:
        return content_type_error

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    category_hint = _safe_text(payload.get("category")).lower()
    resolved_category = None if category_hint in {"", "all"} else category_hint

    cat_key, cfg, obj = _resolve_scraping_item(item_id, resolved_category)
    if not obj or not cfg or not cat_key:
        return JsonResponse({"error": "Scraped item not found"}, status=404)

    raw_fields = payload.get("fields")
    requested_fields = raw_fields if isinstance(raw_fields, dict) else {}

    for field_key in ("title_ar", "description_ar", "location_ar"):
        if field_key in payload:
            requested_fields[field_key] = payload.get(field_key)

    if not requested_fields:
        return JsonResponse({"saved": True, "updated_fields": []})

    model_field_names = {
        field.name
        for field in obj._meta.get_fields()
        if getattr(field, "concrete", False)
    }

    title_field = cfg.get("title_field") or "title"
    description_field = cfg.get("description_field") or "description"

    field_targets = {
        "title_ar": [f"{title_field}_ar", "title_ar", "name_ar", "job_title_ar"],
        "description_ar": [
            f"{description_field}_ar",
            "description_ar",
            "content_ar",
            "summary_ar",
        ],
        "location_ar": ["location_ar", "city_ar"],
    }

    update_fields = []
    updated_logical_fields = []

    for logical_key, raw_value in requested_fields.items():
        if logical_key not in field_targets:
            continue

        cleaned_value = _safe_text(raw_value)
        target_field = ""
        for candidate in field_targets[logical_key]:
            if candidate in model_field_names:
                target_field = candidate
                break

        if not target_field:
            continue

        current_value = _safe_text(getattr(obj, target_field, ""))
        if current_value == cleaned_value:
            continue

        setattr(obj, target_field, cleaned_value)
        update_fields.append(target_field)
        updated_logical_fields.append(logical_key)

    if update_fields:
        if "translation_status" in model_field_names:
            obj.translation_status = "partial"
            update_fields.append("translation_status")

        obj.save(update_fields=list(dict.fromkeys(update_fields)))

    meta = (
        ScrapedItemMeta.objects.filter(category=cat_key)
        .filter(
            Q(item_id=str(obj.pk))
            | Q(item_title__icontains=_safe_text(getattr(obj, title_field, "")))
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if meta is not None and updated_logical_fields:
        has_missing_critical = False
        if "title_ar" in requested_fields and not _safe_text(
            requested_fields.get("title_ar")
        ):
            has_missing_critical = True
        if "description_ar" in requested_fields and not _safe_text(
            requested_fields.get("description_ar")
        ):
            has_missing_critical = True

        meta.translation_status = "partial" if has_missing_critical else "translated"
        meta.save(update_fields=["translation_status"])

    return JsonResponse(
        {
            "saved": True,
            "updated_fields": list(dict.fromkeys(updated_logical_fields)),
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=120, period_seconds=60, scope="action")
def reject_scraping_item_api(request, item_id):
    """POST /scraping/api/reject/<item_id>/ for soft-reject moderation decisions."""
    _log_scraping_action(request)

    payload = {}
    if request.content_type and "application/json" in request.content_type.lower():
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    else:
        payload = request.POST

    category_hint = _safe_text(payload.get("category")).lower()
    resolved_category = None if category_hint in {"", "all"} else category_hint
    cat_key, cfg, obj = _resolve_scraping_item(item_id, resolved_category)

    if not obj or not cfg or not cat_key:
        return JsonResponse({"error": "Scraped item not found"}, status=404)

    reason_code = _safe_text(payload.get("reason")).lower() or "other"
    reason_other = _safe_text(payload.get("reason_other"))
    reject_notes = (
        reason_other
        if reason_other
        else _safe_text(payload.get("notes") or payload.get("note"))
    )

    affected = _apply_scraping_item_action(
        obj,
        cfg,
        action="reject",
        category=cat_key,
        reject_reason=reason_code,
        reject_notes=reject_notes,
        user=request.user,
    )
    if not affected:
        return JsonResponse({"error": "Reject operation failed"}, status=500)

    normalized_reason_code = _normalize_reject_reason_code(reason_code)
    rejection_reason = _build_rejection_reason_text(
        normalized_reason_code, reject_notes
    )

    next_item_url = _safe_next_url(request, payload.get("next_item_url"))

    return JsonResponse(
        {
            "rejected": True,
            "reason_code": normalized_reason_code,
            "reason": rejection_reason,
            "next_url": next_item_url,
        }
    )


# API aliases for the normalized scraping URL namespace.
api_translate_field = translate_field_api
api_save_draft = save_draft_api
api_reject_item = reject_scraping_item_api


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def scraping_results_bulk_action(request):
    """POST /scraping/results/bulk-action/ for validate/reject/delete actions."""
    _log_scraping_action(request)

    category_map = _scraping_result_category_map()

    filters = _extract_results_filters(request.POST)
    category_hint = filters["category"]
    query = filters["q"]
    run_id = filters["run_id"]

    if category_hint != "all" and category_hint not in category_map:
        category_hint = "all"

    selected_run = None
    if run_id:
        selected_run = ScrapingRun.objects.filter(pk=run_id).first()
        if selected_run is None:
            run_id = ""

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"validate", "reject", "delete"}:
        messages.warning(request, "Invalid bulk action.")
        return redirect(
            _results_redirect_url(
                category_hint,
                query,
                run_id=run_id,
                extra_params=filters,
            )
        )

    all_matching = _as_bool(request.POST.get("all_matching"), default=False)
    reject_reason = request.POST.get("reject_reason", "other")
    reject_notes = request.POST.get("reject_notes", "")

    item_tokens = _split_item_tokens(request.POST.getlist("item_ids"))
    if not item_tokens:
        item_tokens = _split_item_tokens(request.POST.getlist("selected_items"))

    if all_matching:
        dataset = _build_scraping_results_dataset(
            category_map,
            selected_category=category_hint,
            selected_run=selected_run,
            query=query,
            selected_source=filters["source"],
            confidence_filter=filters["confidence"],
            translation_filter=filters["translation"],
            date_range=filters["date_range"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            selected_run_id=run_id,
        )
        item_tokens = [row["selection_key"] for row in dataset["rows"]]

    if not item_tokens:
        messages.warning(request, "No items selected.")
        return redirect(
            _results_redirect_url(
                category_hint,
                query,
                run_id=run_id,
                extra_params=filters,
            )
        )

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
            obj,
            cfg,
            action=action,
            category=cat_key,
            reject_reason=reject_reason,
            reject_notes=reject_notes,
            user=request.user,
        )

    if action == "validate":
        messages.success(request, f"Published {affected_total} selected item(s).")
    elif action == "reject":
        messages.success(request, f"Rejected {affected_total} selected item(s).")
    else:
        messages.success(request, f"Deleted {affected_total} selected item(s).")

    return redirect(
        _results_redirect_url(
            category_hint,
            query,
            run_id=run_id,
            extra_params=filters,
        )
    )


@login_required
@user_passes_test(is_admin)
def scraping_results(request):
    """Staff review queue for scraped items across categories."""
    _log_scraping_action(request)

    if request.method == "POST":
        return scraping_results_bulk_action(request)

    category_map = _scraping_result_category_map()

    filters = _extract_results_filters(request.GET)
    selected_category = filters["category"]
    if selected_category != "all" and selected_category not in category_map:
        selected_category = "all"

    query = filters["q"]
    selected_run_id = filters["run_id"]
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
            if selected_category not in category_map:
                return JsonResponse(
                    {
                        "error": (
                            "Review not yet available for category "
                            f"'{selected_category}'."
                        ),
                        "action": "contact_admin",
                    },
                    status=400,
                )

    dataset = _build_scraping_results_dataset(
        category_map,
        selected_category=selected_category,
        selected_run=selected_run,
        query=query,
        selected_source=filters["source"],
        confidence_filter=filters["confidence"],
        translation_filter=filters["translation"],
        date_range=filters["date_range"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        selected_run_id=selected_run_id,
    )

    rows = dataset["rows"]
    pending_counts = dataset["pending_counts"]
    source_options = dataset["source_options"]
    filtered_total = dataset["filtered_total"]
    filtered_category_counts = dataset["filtered_category_counts"]
    filtered_low_confidence_count = dataset["filtered_low_confidence_count"]

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="scraping_queue_export.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "title_en",
                "title_ar",
                "category",
                "confidence",
                "translation_status",
                "source_url",
                "scraped_at",
                "run_id",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["item_id"],
                    row.get("title_en", ""),
                    row.get("title_ar", ""),
                    row.get("category", ""),
                    ""
                    if row.get("confidence_score") is None
                    else row["confidence_score"],
                    row.get("translation_state", ""),
                    row.get("source_url", ""),
                    row.get("scraped_date").isoformat()
                    if row.get("scraped_date")
                    else "",
                    row.get("run_id", selected_run_id),
                ]
            )
        return response

    per_page = int(filters["per_page"])
    page_number = filters["page"]
    paginator = Paginator(rows, per_page)
    page_obj = paginator.get_page(page_number)
    previous_page = page_obj.previous_page_number() if page_obj.has_previous() else 1
    next_page = (
        page_obj.next_page_number() if page_obj.has_next() else paginator.num_pages
    )

    current_filters = {
        "category": selected_category,
        "q": query,
        "run_id": selected_run_id,
        "source": filters["source"],
        "confidence": filters["confidence"],
        "translation": filters["translation"],
        "date_range": filters["date_range"],
        "date_from": filters["date_from_raw"],
        "date_to": filters["date_to_raw"],
        "per_page": filters["per_page"],
        "page": str(page_obj.number),
    }

    export_params = {}
    for key, value in current_filters.items():
        if key == "page":
            continue
        if value in {None, "", "any"}:
            continue
        if key == "category" and value == "all":
            continue
        export_params[key] = value
    export_params["export"] = "csv"
    export_url = reverse("scraping:scraping_results") + "?" + urlencode(export_params)

    recent_runs_qs = ScrapingRun.objects.filter(
        category__in=category_map.keys()
    ).order_by("-started_at")[:120]
    run_filter_options = [
        {
            "id": str(run.id),
            "category": run.category,
            "status": run.status,
            "started_at": run.started_at,
            "label": (
                f"{str(run.id)[:8]} · {run.category.title()} · "
                f"{run.started_at:%Y-%m-%d %H:%M}"
            ),
        }
        for run in recent_runs_qs
    ]

    category_tabs = []
    for key, cfg in category_map.items():
        meta = CATEGORY_META.get(key, {})
        category_tabs.append(
            {
                "key": key,
                "label": cfg["label"],
                "count": pending_counts.get(key, 0),
                "color": meta.get("color", "#2563eb"),
                "icon": meta.get("icon", "fa-circle"),
            }
        )

    if selected_category == "all":
        resolved_category_key = "all"
        resolved_category_label = str(_("All categories"))
    else:
        resolved_category_key = selected_category
        resolved_category_label = (
            category_map.get(resolved_category_key, {}).get("label")
            or CATEGORY_META.get(resolved_category_key, {}).get("label")
            or resolved_category_key.title()
        )
    category_global_status = "warn" if filtered_low_confidence_count > 0 else "ok"
    category_global_status_label = (
        str(_("Global status: Needs attention"))
        if category_global_status == "warn"
        else str(_("Global status: OK"))
    )
    pending_total = (
        pending_counts.get(selected_category, 0)
        if selected_category != "all"
        else sum(pending_counts.values())
    )

    return render(
        request,
        "scraping/results.html",
        {
            "page_obj": page_obj,
            "paginator": paginator,
            "rows": page_obj.object_list,
            "filtered_total": filtered_total,
            "selected_category": selected_category,
            "selected_run_id": selected_run_id,
            "selected_run": selected_run,
            "search_query": query,
            "current_filters": current_filters,
            "run_filter_options": run_filter_options,
            "source_options": source_options,
            "page_size_options": [25, 50, 100],
            "previous_page": previous_page,
            "next_page": next_page,
            "category_tabs": category_tabs,
            "pending_total": pending_total,
            "filtered_category_counts_json": json.dumps(filtered_category_counts),
            "filtered_low_confidence_count": filtered_low_confidence_count,
            "export_url": export_url,
            "category_key": resolved_category_key,
            "category_name": resolved_category_label,
            "category_active_tab": "pending",
            "category_global_status": category_global_status,
            "category_global_status_label": category_global_status_label,
            "page": "scraping",
            **_scraping_shell_context(request, active_page="results"),
        },
    )


@login_required
@user_passes_test(is_admin)
def scraping_result_detail(request, item_id):
    """Professional moderation detail page with inline Arabic editing."""
    _log_scraping_action(request)

    category_map = _scraping_result_category_map()
    filters = _extract_results_filters(request.GET)
    queue_category = filters["category"]
    if queue_category != "all" and queue_category not in category_map:
        queue_category = "all"

    item_category_hint = _safe_text(
        request.GET.get("item_category") or request.GET.get("category")
    ).lower()
    if item_category_hint == "all":
        item_category_hint = ""

    selected_run_id = _safe_text(filters.get("run_id"))
    selected_run = None
    if selected_run_id:
        selected_run = ScrapingRun.objects.filter(pk=selected_run_id).first()
        if selected_run is None:
            selected_run_id = ""
        elif selected_run.category in category_map:
            queue_category = selected_run.category

    category_for_lookup = item_category_hint or None
    cat_key, cfg, obj = _resolve_scraping_item(item_id, category_for_lookup)
    if not obj or not cfg or not cat_key:
        raise Http404("Scraped review item not found")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action in {"validate", "reject", "delete"}:
            _apply_scraping_item_action(
                obj,
                cfg,
                action=action,
                category=cat_key,
                reject_reason=request.POST.get("reject_reason", "other"),
                reject_notes=request.POST.get("reject_notes", ""),
                user=request.user,
            )

        return redirect(
            _results_redirect_url(
                queue_category,
                filters["q"],
                run_id=selected_run_id,
                extra_params=filters,
            )
        )

    detail_filters = dict(filters)
    detail_filters["category"] = queue_category
    detail_filters["run_id"] = selected_run_id

    dataset = _build_scraping_results_dataset(
        category_map,
        selected_category=queue_category,
        selected_run=selected_run,
        query=detail_filters["q"],
        selected_source=detail_filters["source"],
        confidence_filter=detail_filters["confidence"],
        translation_filter=detail_filters["translation"],
        date_range=detail_filters["date_range"],
        date_from=detail_filters["date_from"],
        date_to=detail_filters["date_to"],
        selected_run_id=selected_run_id,
    )
    queue_rows = dataset["rows"]

    current_selection_key = f"{cat_key}:{obj.pk}"
    current_index = -1
    for index, row in enumerate(queue_rows):
        if row["selection_key"] == current_selection_key:
            current_index = index
            break

    if current_index < 0:
        for index, row in enumerate(queue_rows):
            if row["item_id"] == str(obj.pk) and row["category"] == cat_key:
                current_index = index
                break

    filtered_total = len(queue_rows)
    position_index = current_index + 1 if current_index >= 0 else 1

    prev_row = queue_rows[current_index - 1] if current_index > 0 else None
    next_row = (
        queue_rows[current_index + 1]
        if current_index >= 0 and current_index + 1 < filtered_total
        else None
    )
    prev_url = (
        _build_result_detail_url(
            prev_row["item_id"],
            item_category=prev_row["category"],
            filters=detail_filters,
        )
        if prev_row
        else ""
    )
    next_url = (
        _build_result_detail_url(
            next_row["item_id"],
            item_category=next_row["category"],
            filters=detail_filters,
        )
        if next_row
        else ""
    )

    model_field_names = {
        field.name
        for field in obj._meta.get_fields()
        if getattr(field, "concrete", False)
    }

    title_field = cfg["title_field"]
    description_field = cfg["description_field"]
    source_field = cfg["source_field"]
    date_field = cfg["date_field"]
    status_field = cfg["status_field"]

    title_en = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            f"{title_field}_en",
            "title_en",
            "name_en",
            "job_title_en",
            title_field,
            "title",
            "name",
            "job_title",
            "dataset_name",
        ],
        default=str(obj),
    )
    title_ar = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            f"{title_field}_ar",
            "title_ar",
            "name_ar",
            "job_title_ar",
            "dataset_name_ar",
        ],
        default="",
    )

    description_en = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            f"{description_field}_en",
            "description_en",
            "content_en",
            "summary_en",
            description_field,
            "description",
            "content",
            "summary",
        ],
        default="",
    )
    description_ar = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            f"{description_field}_ar",
            "description_ar",
            "content_ar",
            "summary_ar",
        ],
        default="",
    )

    location_field = cfg.get("location_field") or ""
    location_en = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            "location_en",
            location_field,
            "location",
            "city",
        ],
        default="",
    )
    location_ar = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=["location_ar", "city_ar"],
        default="",
    )
    has_location = bool(location_en or location_ar)

    source_url = _first_available_text(
        obj,
        model_field_names=model_field_names,
        candidates=[
            source_field,
            "source_url",
            "website",
            "access_link",
            "enrollment_url",
            "url",
            "download_url",
        ],
        default="",
    )
    source_domain = (urlparse(source_url).netloc or "").lower()

    scraped_date = getattr(obj, date_field, None)
    raw_status = _safe_text(getattr(obj, status_field, "pending")) or "pending"

    confidence_score = None
    confidence_field = cfg.get("confidence_field")
    if confidence_field and confidence_field in model_field_names:
        confidence_score = getattr(obj, confidence_field, None)

    meta = (
        ScrapedItemMeta.objects.filter(category=cat_key)
        .filter(Q(item_id=str(obj.pk)) | Q(item_title=title_en))
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if meta and meta.relevance_score is not None:
        confidence_score = meta.relevance_score
    if confidence_score is not None:
        confidence_score = round(float(confidence_score), 2)

    domain_scores = {}
    if meta is not None and isinstance(meta.domain_scores, dict):
        domain_scores = meta.domain_scores

    raw_translation_status = ""
    if "translation_status" in model_field_names:
        raw_translation_status = _safe_text(getattr(obj, "translation_status", ""))
    if not raw_translation_status and meta is not None:
        raw_translation_status = _safe_text(meta.translation_status)

    title_translation_state = _translation_state_for_pair(
        source_text=title_en,
        target_text=title_ar,
        raw_translation_status=raw_translation_status,
    )
    description_translation_state = _translation_state_for_pair(
        source_text=description_en,
        target_text=description_ar,
        raw_translation_status=raw_translation_status,
    )
    location_translation_state = _translation_state_for_pair(
        source_text=location_en,
        target_text=location_ar,
        raw_translation_status=raw_translation_status,
    )

    from scraping.intelligence import ConfidenceCalculator
    calc = ConfidenceCalculator()

    title_en_score = int(calc.score_field(title_en, "title") * 100)
    description_en_score = int(calc.score_field(description_en, "description") * 100)
    date_score = int(calc.score_field(str(scraped_date or ""), "date") * 100)
    location_score = int(calc.score_field(location_en, "location") * 100)
    url_score = int(calc.score_field(source_url, "url") * 100)

    row_data = {
        "title_en": title_en, "title": title_en,
        "description_en": description_en, "description": description_en,
        "url": source_url, "source_url": source_url,
        "start_date": scraped_date, "scraped_date": scraped_date,
        "location_en": location_en, "location": location_en,
    }
    _extra_fields = (
        "job_title", "dataset_name", "platform", "level", "price",
        "institution_name", "deadline", "paper_url", "download_url",
        "published_date", "access_link"
    )
    for _ef in _extra_fields:
        if _ef in model_field_names:
            row_data[_ef] = getattr(obj, _ef, None)

    calc_report = calc.calculate(cat_key, row_data)

    if confidence_score is None or confidence_score <= 0:
        confidence_score = calc_report["percent"]

    overall_confidence = confidence_score
    if overall_confidence is None:
        overall_confidence = 0.0

    breakdown_rows = [
        {
            "key": "title_en",
            "label": "Title EN",
            "score": title_en_score,
            "state": _breakdown_state_for_score(title_en_score),
        },
        {
            "key": "description_en",
            "label": "Description EN",
            "score": description_en_score,
            "state": _breakdown_state_for_score(description_en_score),
        },
        {
            "key": "date",
            "label": "Date",
            "score": date_score,
            "state": _breakdown_state_for_score(date_score),
        },
        {
            "key": "url",
            "label": "URL",
            "score": url_score,
            "state": _breakdown_state_for_score(url_score),
        },
    ]

    if has_location:
        breakdown_rows.insert(
            3,
            {
                "key": "location",
                "label": "Location",
                "score": location_score,
                "state": _breakdown_state_for_score(location_score),
            },
        )

    title_ar_target_field = ""
    for candidate in [f"{title_field}_ar", "title_ar", "name_ar", "job_title_ar"]:
        if candidate in model_field_names:
            title_ar_target_field = candidate
            break

    description_ar_target_field = ""
    for candidate in [
        f"{description_field}_ar",
        "description_ar",
        "content_ar",
        "summary_ar",
    ]:
        if candidate in model_field_names:
            description_ar_target_field = candidate
            break

    location_ar_target_field = ""
    for candidate in ["location_ar", "city_ar"]:
        if candidate in model_field_names:
            location_ar_target_field = candidate
            break

    source_name = (
        _safe_text(getattr(meta, "source_name", ""))
        or _safe_text(getattr(obj, "source_name", ""))
        or source_domain
    )

    source_health = None
    if source_name:
        source_health = ScrapingSourceHealth.objects.filter(
            category=cat_key,
            source_name__iexact=source_name,
        ).first()
    if source_health is None and source_domain:
        source_health = (
            ScrapingSourceHealth.objects.filter(
                category=cat_key,
                base_url__icontains=source_domain,
            )
            .order_by("-last_attempt_at")
            .first()
        )

    trust_score = None
    response_seconds = None
    if source_health is not None:
        if source_health.health_score is not None:
            trust_score = round(float(source_health.health_score) / 100.0, 2)
        if source_health.avg_response_time is not None:
            response_seconds = round(float(source_health.avg_response_time), 2)

    translation_states = [title_translation_state, description_translation_state]
    if has_location:
        translation_states.append(location_translation_state)
    translation_total_fields = len(translation_states)
    translated_fields_count = len(
        [state for state in translation_states if state == "translated"]
    )

    translation_status = raw_translation_status
    if not translation_status:
        if (
            translated_fields_count == translation_total_fields
            and translation_total_fields > 0
        ):
            translation_status = "translated"
        elif translated_fields_count > 0:
            translation_status = "partial"
        else:
            copied_fields_count = len(
                [state for state in translation_states if state == "copied"]
            )
            translation_status = "copied" if copied_fields_count > 0 else "missing"

    provenance_warnings = []
    if meta is not None and _safe_text(meta.skip_reason):
        provenance_warnings.append(
            {"key": "skip_reason", "value": _safe_text(meta.skip_reason)}
        )
    if source_health is not None and _safe_text(source_health.last_error):
        provenance_warnings.append(
            {"key": "source_error", "value": _safe_text(source_health.last_error)}
        )

    date_display = ""
    date_display_ar = ""
    if scraped_date is not None:
        if hasattr(scraped_date, "strftime"):
            date_display = scraped_date.strftime("%Y-%m-%d")
            date_display_ar = _to_arabic_digits(date_display)

    ner_entities = _extract_ner_entities(obj, cfg, meta)

    back_url = _results_redirect_url(
        queue_category,
        detail_filters["q"],
        run_id=selected_run_id,
        extra_params=detail_filters,
    )
    fallback_next_url = next_url or back_url

    context_position_total = filtered_total if filtered_total > 0 else 1

    return render(
        request,
        "scraping/result_detail.html",
        {
            "item": obj,
            "item_id": str(obj.pk),
            "category": cat_key,
            "category_label": cfg["label"],
            "queue_category": queue_category,
            "queue_category_label": (
                category_map.get(queue_category, {}).get("label", "All")
                if queue_category != "all"
                else "All"
            ),
            "status_label": _result_status_label(raw_status),
            "status_badge": _result_status_badge(raw_status),
            "overall_confidence": overall_confidence,
            "extracted_confidence": confidence_score,
            "breakdown_rows": breakdown_rows,
            "title_en": title_en,
            "title_ar": title_ar,
            "description_en": description_en,
            "description_ar": description_ar,
            "location_en": location_en,
            "location_ar": location_ar,
            "has_location": has_location,
            "source_url": source_url,
            "source_domain": source_domain,
            "scraped_date": scraped_date,
            "date_display": date_display,
            "date_display_ar": date_display_ar,
            "position_index": position_index,
            "position_total": context_position_total,
            "filtered_total": filtered_total,
            "prev_url": prev_url,
            "next_url": next_url,
            "has_prev": bool(prev_url),
            "has_next": bool(next_url),
            "title_translation_state": title_translation_state,
            "description_translation_state": description_translation_state,
            "location_translation_state": location_translation_state,
            "title_ar_target_field": title_ar_target_field,
            "description_ar_target_field": description_ar_target_field,
            "location_ar_target_field": location_ar_target_field,
            "source_name": source_name,
            "trust_score": trust_score,
            "query_used": detail_filters["q"],
            "run_id": selected_run_id,
            "run_started_at": getattr(selected_run, "started_at", None),
            "llm_model": _safe_text(getattr(settings, "GROQ_SCRAPING_MODEL", ""))
            or "llama-3.3-70b-versatile",
            "llm_response_seconds": response_seconds,
            "translation_status": translation_status,
            "translation_total_fields": translation_total_fields,
            "translated_fields_count": translated_fields_count,
            "provenance_warnings": provenance_warnings,
            "ner_entities": ner_entities,
            "meta": meta,
            "domain_scores": domain_scores,
            "domain_scores_json": json.dumps(domain_scores, ensure_ascii=False),
            "back_url": back_url,
            "fallback_next_url": fallback_next_url,
            "current_filters": detail_filters,
            "translate_field_api_url": reverse("scraping:translate_field_api"),
            "save_draft_api_url": reverse("scraping:save_draft_api", args=[obj.pk]),
            "reject_api_url": reverse(
                "scraping:reject_scraping_item_api", args=[obj.pk]
            ),
            "validate_url": reverse("scraping:scraping_result_validate", args=[obj.pk]),
            "delete_url": reverse("scraping:scraping_result_delete", args=[obj.pk]),
            "page": "scraping",
            **_scraping_shell_context(request, active_page="results"),
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

    if not _check_rate_limit(request, scope="run_trigger", max_calls=10, period=3600):
        return JsonResponse(
            {"error": "Too many run requests. Max 10 per hour."},
            status=429,
            headers={"Retry-After": "3600"},
        )

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
        items_updated=0,
        triggered_by=request.user,
    )

    def _celery_workers_available() -> bool:
        try:
            inspector = current_celery_app.control.inspect(timeout=1)
            pings = inspector.ping() if inspector else None
            return bool(pings)
        except Exception as exc:
            logger.warning(
                "celery_worker_ping_failed",
                extra={"error": str(exc), "context": category},
                exc_info=False,
            )
            return False

    # --- Try async (Celery) execution first, only when workers are available ---
    try:
        if _celery_workers_available():
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
        logger.warning("No Celery workers detected; falling back to synchronous run")

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
        run.items_updated = result.get("items_updated", 0)
        run.items_skipped = result.get("items_skipped", 0)
        result_errors = result.get("errors", [])
        if not isinstance(result_errors, list):
            result_errors = [str(result_errors)] if result_errors else []
        run.errors = "\n".join(str(err) for err in result_errors if err)
        has_items = bool(
            int(run.items_found or 0)
            or int(run.items_created or 0)
            or int(run.items_updated or 0)
        )
        run.status = "failed" if run.errors and not has_items else "completed"
        run.current_message = (
            f"Run Complete: {int(run.items_created or 0)} Created, "
            f"{int(run.items_updated or 0)} Updated, "
            f"{int(run.items_skipped or 0)} Skipped"
        )
        run.completed_at = timezone.now()
        run.save()

        return JsonResponse(
            {
                "status": "error" if run.status == "failed" else "success",
                "run_id": str(run.pk),
                "items_found": run.items_found,
                "items_created": run.items_created,
                "items_updated": run.items_updated,
                "items_skipped": run.items_skipped,
                "errors": result_errors,
                "results": result.get("results", []),
                "duration": run.duration,
                "message": run.current_message,
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
@require_POST
@csrf_protect
def run_quick_scrape(request, category):
    """AJAX endpoint: dispatch quick broad-discovery scrape to Celery."""
    _log_scraping_action(request)

    if not _check_rate_limit(
        request,
        scope="quick_run_trigger",
        max_calls=20,
        period=3600,
    ):
        return JsonResponse(
            {"error": "Too many quick scrape requests. Max 20 per hour."},
            status=429,
            headers={"Retry-After": "3600"},
        )

    staff_error = _require_staff(request)
    if staff_error:
        return staff_error

    if category not in CATEGORY_META:
        return JsonResponse(
            {"status": "error", "message": f"Unknown category: {category}"},
            status=400,
        )

    run = ScrapingRun.objects.create(
        category=category,
        status="running",
        items_updated=0,
        triggered_by=request.user,
        current_source="quick_scrape",
        current_step="Quick scrape: broad web discovery",
        current_message="Quick scrape started",
        progress_total=6,
    )

    def _celery_workers_available() -> bool:
        try:
            inspector = current_celery_app.control.inspect(timeout=1)
            pings = inspector.ping() if inspector else None
            return bool(pings)
        except Exception as exc:
            logger.warning(
                "celery_worker_ping_failed",
                extra={"error": str(exc), "context": category},
                exc_info=False,
            )
            return False

    try:
        if _celery_workers_available():
            async_result = run_quick_scrape_task.delay(
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
                    "mode": "quick_scrape",
                    "message": "Quick scrape dispatched to background worker.",
                }
            )
        logger.warning(
            "No Celery workers detected for quick scrape; falling back to synchronous run"
        )
    except Exception as celery_exc:
        logger.warning(
            "Quick scrape celery dispatch failed (%s); running synchronously",
            celery_exc,
        )

    try:
        result = run_quick_scrape_task.apply(
            kwargs={
                "category": category,
                "run_id": str(run.pk),
                "user_id": request.user.pk,
            }
        ).get()
        return JsonResponse(
            {
                "status": "success",
                "run_id": str(run.pk),
                "mode": "quick_scrape",
                "items_found": int(result.get("items_found", 0) or 0),
                "items_created": int(result.get("items_created", 0) or 0),
                "items_updated": int(result.get("items_updated", 0) or 0),
                "items_skipped": int(result.get("items_skipped", 0) or 0),
                "errors": result.get("errors", []),
                "results": result.get("results", []),
                "duration": run.duration,
                "message": result.get("message") or "Quick scrape completed.",
            }
        )
    except Exception as exc:
        run.status = "failed"
        run.errors = str(exc)
        run.current_source = "quick_scrape"
        run.current_step = str(exc)[:100]
        run.current_message = str(exc)[:255]
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_source",
                "current_step",
                "current_message",
                "completed_at",
            ]
        )
        return JsonResponse(
            {
                "status": "error",
                "mode": "quick_scrape",
                "message": str(exc),
            },
            status=500,
        )


_CUSTOM_ELEMENT_SEARCH_METHOD = {
    "events": "search_events",
    "tools": "search_tools",
    "courses": "search_courses",
    "news": "search_news",
    "opportunities": "search_opportunities",
    "corpus": "search_corpus",
}

_CUSTOM_ELEMENT_LABEL = {
    "events": "event",
    "tools": "tool",
    "courses": "course",
    "news": "news item",
    "opportunities": "opportunity",
    "corpus": "corpus item",
}


def _normalize_custom_element_url(raw_url: str) -> str:
    candidate = str(raw_url or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = f"https://{candidate}"
        parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    return candidate


def _build_custom_element_search_row(element_url: str) -> dict[str, str]:
    response = requests.get(
        element_url,
        timeout=(5, 20),
        headers={"User-Agent": "Mozilla/5.0 NLPPlatformCustomElement/1.0"},
    )
    response.raise_for_status()

    raw_text = response.text or ""
    content_type = str(response.headers.get("Content-Type") or "").lower()

    title = ""
    content = ""
    if "html" in content_type and BeautifulSoup is not None:
        soup = BeautifulSoup(raw_text, "html.parser")
        for tag_name in ("script", "style", "noscript"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        meta_title = soup.find("meta", attrs={"property": "og:title"})
        if meta_title:
            title = str(meta_title.get("content") or "").strip()
        if not title and soup.title:
            title = str(soup.title.get_text(" ", strip=True) or "").strip()

        content = " ".join(soup.stripped_strings)
    else:
        content = re.sub(r"\s+", " ", raw_text or "").strip()

    title = str(title or element_url).strip()[:240]
    content = re.sub(r"\s+", " ", content or "").strip()[:7000]

    if not content and not title:
        raise ValueError("URL fetched but did not provide readable content")

    return {
        "title": title,
        "url": element_url,
        "content": content,
    }


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
def run_custom_element(request, category):
    """Scrape one specific URL through the normal category pipeline."""
    _log_scraping_action(request)

    if not _check_rate_limit(
        request,
        scope="custom_element_trigger",
        max_calls=30,
        period=3600,
    ):
        return JsonResponse(
            {"error": "Too many custom element requests. Max 30 per hour."},
            status=429,
            headers={"Retry-After": "3600"},
        )

    staff_error = _require_staff(request)
    if staff_error:
        return staff_error

    if category not in CATEGORY_META:
        return JsonResponse(
            {"status": "error", "message": f"Unknown category: {category}"},
            status=400,
        )

    payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    element_url = _normalize_custom_element_url(payload.get("url"))
    if not element_url:
        return JsonResponse(
            {
                "status": "error",
                "message": "Please provide a valid http(s) URL.",
            },
            status=400,
        )

    run = ScrapingRun.objects.create(
        category=category,
        status="running",
        items_updated=0,
        triggered_by=request.user,
        current_source="custom_element",
        current_step="Custom element: validating URL",
        current_message="Custom element scrape started",
        current_item=element_url[:255],
        progress_total=3,
    )

    try:
        search_row = _build_custom_element_search_row(element_url)
    except Exception as exc:
        message = f"cant scrap element because URL could not be fetched: {exc}"
        run.status = "failed"
        run.errors = message
        run.current_step = "Custom element: fetch failed"
        run.current_message = message[:255]
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_step",
                "current_message",
                "completed_at",
            ]
        )
        return JsonResponse(
            {
                "status": "error",
                "run_id": str(run.pk),
                "message": message,
            },
            status=400,
        )

    from scraping.network.search_client import TavilySearchClient

    search_method_name = _CUSTOM_ELEMENT_SEARCH_METHOD.get(category)
    if not search_method_name:
        message = "cant scrap element because category pipeline is not available"
        run.status = "failed"
        run.errors = message
        run.current_step = "Custom element: unsupported category"
        run.current_message = message[:255]
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_step",
                "current_message",
                "completed_at",
            ]
        )
        return JsonResponse(
            {
                "status": "error",
                "run_id": str(run.pk),
                "message": message,
            },
            status=400,
        )

    async def _fake_search_method(self, query, max_results=None):
        del self, query, max_results
        return [search_row]

    scraper = get_scraper(category)
    if hasattr(scraper, "bind_progress_run"):
        scraper.bind_progress_run(run)

    try:
        with patch.object(
            scraper,
            "get_active_search_queries",
            return_value=[f"custom_url:{element_url}"],
        ), patch.object(
            TavilySearchClient,
            search_method_name,
            _fake_search_method,
        ):
            result = scraper.run()
    except Exception as exc:
        message = f"cant scrap element because pipeline failed: {exc}"
        run.status = "failed"
        run.errors = message
        run.current_step = "Custom element: scraper failed"
        run.current_message = message[:255]
        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "errors",
                "current_step",
                "current_message",
                "completed_at",
            ]
        )
        logger.exception("Custom element scrape failed for category=%s", category)
        return JsonResponse(
            {
                "status": "error",
                "run_id": str(run.pk),
                "message": message,
            },
            status=500,
        )

    items_found = int(result.get("items_found", 0) or 0)
    items_created = int(result.get("items_created", 0) or 0)
    items_updated = int(result.get("items_updated", 0) or 0)
    items_skipped = int(result.get("items_skipped", 0) or 0)
    result_errors = result.get("errors", [])
    if not isinstance(result_errors, list):
        result_errors = [str(result_errors)] if result_errors else []

    if (items_created + items_updated + items_skipped) <= 0:
        item_label = _CUSTOM_ELEMENT_LABEL.get(category, "item")
        message = (
            f"cant scrap element because its not a {item_label} "
            f"or it failed validation for category '{category}'."
        )
        if result_errors:
            message = f"{message} Details: {' | '.join(str(err) for err in result_errors if err)}"

        run.items_found = items_found
        run.items_created = items_created
        run.items_updated = items_updated
        run.items_skipped = items_skipped
        run.errors = message
        run.status = "failed"
        run.current_source = "custom_element"
        run.current_step = "Custom element: rejected by category validation"
        run.current_message = message[:255]
        run.completed_at = timezone.now()
        run.save()

        return JsonResponse(
            {
                "status": "error",
                "run_id": str(run.pk),
                "message": message,
                "items_found": items_found,
                "items_created": items_created,
                "items_updated": items_updated,
                "items_skipped": items_skipped,
                "errors": result_errors,
            },
            status=422,
        )

    # Success case (including skipped/duplicates)
    if items_skipped > 0 and (items_created + items_updated) == 0:
        message = f"Element validated, but it already exists in the database for {category}."
    else:
        message = f"Successfully scraped {items_created + items_updated} custom {category} element(s)."

    run.items_found = items_found
    run.items_created = items_created
    run.items_updated = items_updated
    run.items_skipped = items_skipped
    run.errors = "\n".join(str(err) for err in result_errors if err)
    run.status = "completed"
    run.current_source = "custom_element"
    run.current_step = "Custom element completed"
    run.current_message = message[:255]
    run.completed_at = timezone.now()
    run.save()
    return JsonResponse(
        {
            "status": "success",
            "mode": "custom_element",
            "run_id": str(run.pk),
            "items_found": items_found,
            "items_created": items_created,
            "items_updated": items_updated,
            "items_skipped": items_skipped,
            "errors": result_errors,
            "results": result.get("results", []),
            "duration": run.duration,
            "message": run.current_message,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=120, period_seconds=60, scope="polling")
def category_stats(request, category):
    """Return card-level stats for one scraping category."""
    _log_scraping_action(request)
    normalized_category = (category or "").strip().lower()
    if normalized_category not in CATEGORY_META:
        return JsonResponse({"error": "Unknown category"}, status=400)

    model_cls = _model_for_category(normalized_category)
    total_items = 0
    pending_items = 0
    if model_cls is not None:
        total_items = model_cls.objects.count()
        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        if "approval_status" in field_names:
            pending_items = model_cls.objects.filter(approval_status="pending").count()
        elif "is_approved" in field_names:
            pending_items = model_cls.objects.filter(is_approved=False).count()

    last_run = (
        ScrapingRun.objects.filter(category=normalized_category)
        .order_by("-started_at")
        .first()
    )
    last_run_status = ""
    if last_run is not None:
        last_run_status = str(last_run.status or "").strip().lower() or "completed"
        if (
            last_run_status == "completed"
            and str(last_run.errors or "").strip()
            and int(last_run.items_found or 0) == 0
        ):
            last_run_status = "failed"
    review_supported_categories = set(_scraping_result_category_map().keys())

    return JsonResponse(
        {
            "category": normalized_category,
            "pending_count": pending_items,
            "total_count": total_items,
            "can_review": normalized_category in review_supported_categories,
            "last_run": (
                {
                    "run_id": str(last_run.id),
                    "status": last_run_status,
                    "started_at": (
                        last_run.started_at.isoformat() if last_run.started_at else None
                    ),
                    "completed_at": (
                        last_run.completed_at.isoformat()
                        if last_run.completed_at
                        else None
                    ),
                    "duration_seconds": last_run.duration,
                    "items_found": int(last_run.items_found or 0),
                    "items_created": int(last_run.items_created or 0),
                    "items_skipped": int(last_run.items_skipped or 0),
                    "error_message": str(last_run.errors or ""),
                }
                if last_run
                else None
            ),
        }
    )


api_category_stats = category_stats


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=60, period_seconds=60, scope="analytics")
def quick_stats(request):
    """Return compact quick stats payload used by the dashboard sidebar."""
    _log_scraping_action(request)
    return JsonResponse(_collect_quick_stats_payload())


def _parse_prompt_suggestions(raw_text: str) -> list[str]:
    """Parse LLM output into a JSON array of non-empty prompt strings."""
    text = str(raw_text or "").strip()
    if not text:
        return []

    candidates: list = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            candidates = parsed
    except (TypeError, json.JSONDecodeError):
        pass

    if not candidates:
        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            try:
                parsed = json.loads(array_match.group(0))
                if isinstance(parsed, list):
                    candidates = parsed
            except (TypeError, json.JSONDecodeError):
                candidates = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        prompt = str(item or "").strip()
        if not prompt:
            continue
        key = prompt.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(prompt)
    return cleaned


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=8, period_seconds=60, scope="action")
def generate_search_prompts(request):
    """Generate high-yield search prompts for one scraping category using Groq."""
    _log_scraping_action(request)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, json.JSONDecodeError):
        payload = request.POST

    category = str(payload.get("category") or "").strip().lower()
    supported_categories = {
        "events",
        "tools",
        "corpus",
        "courses",
        "opportunities",
        "news",
    }
    if category not in supported_categories:
        return JsonResponse({"error": "Unknown category"}, status=400)

    max_active_prompts = _prompt_limit_for_category(category)
    active_count = _active_prompt_count(category)
    remaining_slots = max(0, max_active_prompts - active_count)
    if remaining_slots <= 0:
        return JsonResponse(
            {
                "error": (
                    f"Prompt limit reached for {category} "
                    f"({active_count}/{max_active_prompts})."
                ),
                "max_active_prompts": max_active_prompts,
                "active_count": active_count,
                "remaining_slots": 0,
            },
            status=400,
        )

    existing_prompts = list(
        SearchQuery.objects.filter(category=category, is_active=True)
        .order_by("id")
        .values_list("query_text", flat=True)
    )
    current_year = timezone.now().year
    existing_prompts_list = json.dumps(existing_prompts, ensure_ascii=False)

    system_prompt = (
        "You are an expert NLP data curator specializing in Arabic and MENA "
        "region NLP research. Generate highly effective web search queries "
        "designed to discover maximum new content for a scraping pipeline. "
        "Each query must be distinct, specific, and target sources not "
        "commonly indexed."
    )
    user_prompt = f"""Generate 8 diverse, high-yield search queries for the category: {category}

Rules:
- Each query must be unique and target a different angle (geographic, temporal, linguistic, institutional, event-type)
- Mix English and Arabic queries (at least 2 Arabic queries)
- Include site-specific modifiers for at least 2 queries (site:.edu, site:.ac.*, site:.org, site:github.com, site:huggingface.co)
- Include current year ({current_year}) or next year ({current_year + 1}) in time-sensitive queries
- Target MENA, Maghreb, Gulf region institutions explicitly in at least 1 query
- Do NOT repeat any of these already-used prompts: {existing_prompts_list}

Return ONLY a JSON array of strings. No explanation. No markdown. Example:
["query one", "query two", ...]

Category-specific guidance:
- events: conferences, workshops, shared tasks, challenges, symposiums, seminars, hackathons
- tools: GitHub repos, HuggingFace models, APIs, tokenizers, libraries, datasets tools
- corpus: datasets, annotated corpora, speech corpora, text collections, benchmarks
- courses: MOOCs, university courses, bootcamps, certifications, training programs
- opportunities: PhD positions, postdocs, research internships, NLP job openings, grants
- news: research papers, arXiv preprints, tech news, government AI initiatives, lab announcements
"""

    try:
        # Use a longer timeout for generation as it can be slow
        llm_client = GroqLLMClient(timeout=30, max_retries=1)
        llm_text = llm_client._chat_with_groq(system_prompt, user_prompt)
    except Exception as exc:
        logger.warning(
            "generate_search_prompts_call_failed",
            extra={"category": category, "error": str(exc)},
            exc_info=False,
        )
        return JsonResponse({"error": "LLM call failed"}, status=502)

    prompts = _parse_prompt_suggestions(llm_text)
    if not prompts:
        return JsonResponse({"error": "Could not parse prompts"}, status=502)

    return JsonResponse(
        {
            "prompts": prompts[: min(8, remaining_slots)],
            "max_active_prompts": max_active_prompts,
            "active_count": active_count,
            "remaining_slots": remaining_slots,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=30, period_seconds=60, scope="action")
def add_prompt_api(request):
    """Create or update one search prompt row without reloading the page."""
    _log_scraping_action(request)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, json.JSONDecodeError):
        payload = request.POST

    category = str(payload.get("category") or "").strip().lower()
    query_text = str(payload.get("query_text") or "").strip()
    is_active = _as_bool(payload.get("is_active"), default=True)

    if category not in CATEGORY_META:
        return JsonResponse({"error": "Unknown category"}, status=400)
    if not query_text:
        return JsonResponse({"error": "query_text is required"}, status=400)

    max_active_prompts = _prompt_limit_for_category(category)
    active_count = _active_prompt_count(category)
    query_obj = (
        SearchQuery.objects.filter(category=category, query_text=query_text)
        .order_by("id")
        .first()
    )
    created = False

    if query_obj is None:
        if is_active and active_count >= max_active_prompts:
            return JsonResponse(
                {
                    "error": (
                        f"Prompt limit reached for {category} "
                        f"({active_count}/{max_active_prompts})."
                    ),
                    "max_active_prompts": max_active_prompts,
                    "active_count": active_count,
                },
                status=400,
            )
        query_obj = SearchQuery.objects.create(
            category=category,
            query_text=query_text,
            is_active=is_active,
        )
        created = True
    elif query_obj.is_active != is_active:
        if is_active and active_count >= max_active_prompts:
            return JsonResponse(
                {
                    "error": (
                        f"Prompt limit reached for {category} "
                        f"({active_count}/{max_active_prompts})."
                    ),
                    "max_active_prompts": max_active_prompts,
                    "active_count": active_count,
                },
                status=400,
            )
        query_obj.is_active = is_active
        query_obj.save(update_fields=["is_active"])

    updated_active_count = _active_prompt_count(category)

    return JsonResponse(
        {
            "id": str(query_obj.id),
            "category": query_obj.category,
            "query_text": query_obj.query_text,
            "is_active": bool(query_obj.is_active),
            "created": created,
            "max_active_prompts": max_active_prompts,
            "active_count": updated_active_count,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=60, period_seconds=60, scope="action")
def toggle_prompt_api(request, query_id):
    """Toggle one prompt active state (or set explicitly) for inline prompt chips."""
    _log_scraping_action(request)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, json.JSONDecodeError):
        payload = request.POST

    query_obj = SearchQuery.objects.filter(id=query_id).first()
    if query_obj is None:
        return JsonResponse({"error": "Prompt not found"}, status=404)

    explicit_value = payload.get("is_active", None)
    if explicit_value is None:
        query_obj.is_active = not query_obj.is_active
    else:
        query_obj.is_active = _as_bool(explicit_value, default=False)
    query_obj.save(update_fields=["is_active"])

    return JsonResponse(
        {
            "id": str(query_obj.id),
            "category": query_obj.category,
            "query_text": query_obj.query_text,
            "is_active": bool(query_obj.is_active),
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=60, period_seconds=60, scope="action")
def delete_prompt_api(request, query_id):
    """Hard-delete one prompt from the database."""
    _log_scraping_action(request)

    query_obj = SearchQuery.objects.filter(id=query_id).first()
    if query_obj is None:
        return JsonResponse({"error": "Prompt not found"}, status=404)

    category = query_obj.category
    query_obj.is_active = False
    query_obj.save(update_fields=["is_active"])

    updated_active_count = _active_prompt_count(category)
    max_active_prompts = _prompt_limit_for_category(category)

    return JsonResponse(
        {
            "id": str(query_id),
            "deleted": True,
            "active_count": updated_active_count,
            "max_active_prompts": max_active_prompts,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=10, period_seconds=60, scope="action")
def stop_scraping_run(request, run_id):
    """Stop one active run and mark it as failed with a stop reason."""
    _log_scraping_action(request)

    run = ScrapingRun.objects.filter(pk=run_id).first()
    if run is None:
        return JsonResponse({"error": "Run not found"}, status=404)

    if run.status != "running":
        return JsonResponse(
            {
                "status": run.status,
                "run_id": str(run.id),
                "message": "Run is not active.",
            }
        )

    stop_reason = "Stopped by admin"
    if run.task_id:
        try:
            AsyncResult(run.task_id).revoke(terminate=True)
        except Exception as exc:
            logger.warning(
                "stop_run_revoke_failed",
                extra={"error": str(exc), "context": str(run.id)},
                exc_info=False,
            )

    if run.errors:
        if stop_reason not in run.errors:
            run.errors = f"{run.errors}\n{stop_reason}"
    else:
        run.errors = stop_reason

    run.status = "failed"
    run.current_step = stop_reason
    run.current_message = stop_reason
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "errors",
            "current_step",
            "current_message",
            "completed_at",
        ]
    )

    try:
        push_scraping_progress(
            str(run.id),
            status="failed",
            step="stopped",
            progress_current=int(run.progress_current or 0),
            progress_total=int(run.progress_total or 0),
            items_scraped=int(run.items_created or 0),
            items_failed=int(getattr(run, "items_failed", run.items_skipped) or 0),
            current_source=run.current_source or "",
            current_step=run.current_step,
            message=stop_reason,
        )
    except Exception as exc:
        logger.debug("stop_run_progress_emit_failed: %s", exc)

    review_url = f"{reverse('scraping:scraping_results')}?run_id={run.id}"
    return JsonResponse(
        {
            "status": "stopped",
            "run_id": str(run.id),
            "message": stop_reason,
            "review_url": review_url,
        }
    )


@login_required
@staff_member_required
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
        "step": run.current_step or "",
        "message": getattr(run, "current_message", "") or run.current_step or "",
        "current": int(run.progress_current or 0),
        "total": int(run.progress_total or 0),
        "percent": (
            int((int(run.progress_current or 0) / int(run.progress_total or 0)) * 100)
            if int(run.progress_total or 0) > 0
            else 0
        ),
        "progress": int(run.progress_current or 0),
        "progress_current": int(run.progress_current or 0),
        "progress_total": int(run.progress_total or 0),
        "current_step": run.current_step or "",
        "current_message": getattr(run, "current_message", "")
        or run.current_step
        or "",
        "current_source": run.current_source or "",
        "current_item": getattr(run, "current_item", run.current_source) or "",
        "items_found": run.items_found,
        "items_created": run.items_created,
        "items_updated": run.items_updated,
        "items_skipped": run.items_skipped,
        "items_failed": int(getattr(run, "items_failed", run.items_skipped) or 0),
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

        items_updated = int(getattr(scraper, "items_updated", 0) or 0)
        raw_items_created = getattr(scraper, "items_created", None)
        if raw_items_created is None:
            items_created = max(0, int(len(results) or 0) - items_updated)
        else:
            items_created = int(raw_items_created or 0)
        items_failed = getattr(scraper, "items_failed", 0)
        run_complete_message = (
            f"Run Complete: {int(items_created or 0)} Created, "
            f"{int(items_updated or 0)} Updated, {int(items_failed or 0)} Skipped"
        )

        # Determine real status based on results
        if items_created == 0 and items_updated == 0 and items_failed > 0:
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
                "success": items_created > 0 or items_updated > 0 or items_failed == 0,
                "items_created": items_created,
                "items_updated": int(items_updated or 0),
                "items_skipped": int(items_failed or 0),
                "items_failed": items_failed,
                "run_status": run_status,
                "source_name": source.name,
                "message": run_complete_message,
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
@staff_member_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def scraping_analytics_page(request):
    """Render analytics page for browsers; return JSON data for API callers."""
    _log_scraping_action(request)

    window = _parse_analytics_date_window(request)

    if (request.GET.get("export") or "").strip().lower() == "csv":
        payload = _collect_analytics_payload(window)
        return _export_analytics_csv(payload)

    wants_json = (request.GET.get("format") or "").strip().lower() == "json"
    if wants_json or not _request_prefers_html(request):
        return _analytics_json_response(request, window=window)

    completed_runs_count = ScrapingRun.objects.filter(status="completed").count()
    selected_category = _resolve_scraping_selected_category(request)
    if selected_category:
        category_key = selected_category
        category_name = str(
            _(
                (CATEGORY_META.get(category_key, {}) or {}).get(
                    "label", category_key.title()
                )
            )
        )
    else:
        category_key = "all"
        category_name = str(_("All categories"))
    category_meta = {
        category: {
            "label": str(
                _(CATEGORY_META.get(category, {}).get("label", category.title()))
            ),
            "color": _source_color_token(category),
        }
        for category in CATEGORY_META
    }
    is_rtl_lang = str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar")

    context = {
        "page": "scraping",
        "completed_runs_count": completed_runs_count,
        "has_enough_data": completed_runs_count >= 3,
        "initial_analytics_payload_json": json.dumps(
            _collect_analytics_payload(window)
        ),
        "default_range": window["range"],
        "default_date_from": window["start_date"].isoformat(),
        "default_date_to": window["end_date"].isoformat(),
        "category_meta_json": json.dumps(category_meta),
        "category_key": category_key,
        "category_name": category_name,
        "category_active_tab": "analytics",
        "category_global_status": "ok" if completed_runs_count >= 1 else "warn",
        "category_global_status_label": (
            ("الحالة العامة: جيد" if is_rtl_lang else str(_("Global status: OK")))
            if completed_runs_count >= 1
            else (
                "الحالة العامة: بيانات غير كافية"
                if is_rtl_lang
                else str(_("Global status: Insufficient data"))
            )
        ),
        **_scraping_shell_context(request, active_page="analytics"),
    }
    return render(request, "scraping/analytics.html", context)


def _request_prefers_html(request) -> bool:
    if (request.GET.get("view") or "").strip().lower() == "page":
        return True

    accept_header = (request.headers.get("Accept") or "").lower()
    return "text/html" in accept_header and "application/json" not in accept_header


def _parse_analytics_date_window(request) -> dict:
    range_key = (request.GET.get("range") or "30").strip().lower()
    if range_key not in {"7", "30", "90", "custom"}:
        range_key = "30"

    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    end_date = today

    if range_key in {"7", "30", "90"}:
        days = int(range_key)
        start_date = today - timedelta(days=days - 1)
        end_date = today
    else:
        custom_from = _parse_date_param(request.GET.get("date_from"))
        custom_to = _parse_date_param(request.GET.get("date_to"))
        if custom_from and custom_to and custom_from <= custom_to:
            start_date = custom_from
            end_date = custom_to
        else:
            range_key = "30"
            start_date = today - timedelta(days=29)
            end_date = today

    days = max(1, (end_date - start_date).days + 1)
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=days - 1)

    range_label_map = {
        "7": _("Last 7 days"),
        "30": _("Last 30 days"),
        "90": _("Last 90 days"),
        "custom": _("Custom"),
    }

    return {
        "range": range_key,
        "range_label": str(range_label_map.get(range_key, _("Last 30 days"))),
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "prev_start_date": prev_start_date,
        "prev_end_date": prev_end_date,
    }


def _apply_date_window(queryset, field_name: str, window: dict):
    return queryset.filter(
        **{
            f"{field_name}__date__gte": window["start_date"],
            f"{field_name}__date__lte": window["end_date"],
        }
    )


def _run_items_scraped_count(run: ScrapingRun) -> int:
    found = int(run.items_found or 0)
    if found > 0:
        return found
    return (
        int(run.items_created or 0)
        + int(run.items_updated or 0)
        + int(run.items_skipped or 0)
    )


def _safe_percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator) * 100.0


def _metric_delta_payload(
    current_value: float,
    previous_value: float,
    *,
    higher_is_better: bool,
) -> dict:
    if previous_value <= 0:
        raw_change = 0.0 if current_value == 0 else 100.0
    else:
        raw_change = ((current_value - previous_value) / previous_value) * 100.0

    if current_value > previous_value:
        direction = "up"
    elif current_value < previous_value:
        direction = "down"
    else:
        direction = "flat"

    improving = (
        current_value >= previous_value
        if higher_is_better
        else current_value <= previous_value
    )

    return {
        "change_pct": round(abs(raw_change), 1),
        "direction": direction,
        "improving": improving,
    }


def _normalize_rejection_reason(reason_text: str) -> str:
    value = str(reason_text or "").strip().lower()
    if not value:
        return "other"

    if any(
        term in value for term in ["irrelevant", "not relevant", "off-topic", "hors"]
    ):
        return "irrelevant"
    if any(term in value for term in ["arabic", "translation", "لغة", "traduction"]):
        return "poor_arabic"
    if any(
        term in value for term in ["duplicate", "dup", "already exists", "existing"]
    ):
        return "duplicate"
    if any(term in value for term in ["source", "spam", "broken", "invalid url"]):
        return "bad_source"
    return "other"


def _collect_basic_kpis(window: dict, category_cfg_map: dict) -> dict:
    completed_runs = _apply_date_window(
        ScrapingRun.objects.filter(status="completed"),
        "started_at",
        window,
    )

    total_scraped = sum(_run_items_scraped_count(run) for run in completed_runs)

    durations = []
    for run in completed_runs.only("started_at", "completed_at"):
        if run.started_at and run.completed_at:
            durations.append((run.completed_at - run.started_at).total_seconds())
    avg_run_duration_seconds = (
        round(sum(durations) / len(durations), 2) if durations else 0.0
    )

    period_meta_qs = ScrapedItemMeta.objects.filter(
        created_at__date__gte=window["start_date"],
        created_at__date__lte=window["end_date"],
    )
    avg_confidence = float(
        period_meta_qs.aggregate(avg=Avg("relevance_score"))["avg"] or 0.0
    )

    dedup_meta = period_meta_qs.filter(
        was_skipped=True, skip_reason__startswith="dedup_"
    )
    duplicate_rate = _safe_percentage(dedup_meta.count(), period_meta_qs.count())

    approved_total = 0
    reviewed_total = 0

    for cfg in category_cfg_map.values():
        model_cls = cfg.get("model")
        status_field = cfg.get("status_field")
        source_field = cfg.get("source_field")
        date_field = cfg.get("date_field")
        if not model_cls or not status_field or not date_field:
            continue

        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }

        category_qs = model_cls.objects.all()
        if source_field and source_field in field_names:
            category_qs = category_qs.exclude(
                **{f"{source_field}__isnull": True}
            ).exclude(**{source_field: ""})

        category_qs = _apply_date_window(category_qs, date_field, window)
        reviewed_total += category_qs.count()
        approved_total += category_qs.filter(**{status_field: "approved"}).count()

    approval_rate = _safe_percentage(approved_total, reviewed_total)

    return {
        "total_scraped": int(total_scraped),
        "approval_rate": round(approval_rate, 1),
        "avg_confidence": round(avg_confidence, 1),
        "duplicate_rate": round(duplicate_rate, 1),
        "avg_run_duration_seconds": round(avg_run_duration_seconds, 2),
    }


def _collect_analytics_payload(window: dict) -> dict:
    category_cfg_map = _scraping_result_category_map()
    category_keys = list(CATEGORY_META.keys())

    current_basic = _collect_basic_kpis(window, category_cfg_map)
    previous_basic = _collect_basic_kpis(
        {
            "start_date": window["prev_start_date"],
            "end_date": window["prev_end_date"],
        },
        category_cfg_map,
    )

    kpis = {
        "total_scraped": {
            "value": int(current_basic["total_scraped"]),
            **_metric_delta_payload(
                current_basic["total_scraped"],
                previous_basic["total_scraped"],
                higher_is_better=True,
            ),
        },
        "approval_rate": {
            "value": float(current_basic["approval_rate"]),
            **_metric_delta_payload(
                current_basic["approval_rate"],
                previous_basic["approval_rate"],
                higher_is_better=True,
            ),
        },
        "avg_confidence": {
            "value": float(current_basic["avg_confidence"]),
            **_metric_delta_payload(
                current_basic["avg_confidence"],
                previous_basic["avg_confidence"],
                higher_is_better=True,
            ),
        },
        "duplicate_rate": {
            "value": float(current_basic["duplicate_rate"]),
            **_metric_delta_payload(
                current_basic["duplicate_rate"],
                previous_basic["duplicate_rate"],
                higher_is_better=False,
            ),
        },
        "avg_run_duration_seconds": {
            "value": float(current_basic["avg_run_duration_seconds"]),
            **_metric_delta_payload(
                current_basic["avg_run_duration_seconds"],
                previous_basic["avg_run_duration_seconds"],
                higher_is_better=False,
            ),
        },
    }

    by_category = {}
    approval_by_category = []
    skip_values = [choice[0] for choice in ScrapedItemMeta.SKIP_REASON_CHOICES]

    period_meta_qs = ScrapedItemMeta.objects.filter(
        created_at__date__gte=window["start_date"],
        created_at__date__lte=window["end_date"],
    )

    for category in category_keys:
        runs = _apply_date_window(
            ScrapingRun.objects.filter(category=category),
            "started_at",
            window,
        )
        completed_runs = runs.filter(status="completed")

        total_runs = runs.count()
        total_saved = int(
            completed_runs.aggregate(total=Sum("items_created"))["total"] or 0
        )
        total_skipped = int(
            completed_runs.aggregate(total=Sum("items_skipped"))["total"] or 0
        )

        durations = []
        for run in completed_runs.only("started_at", "completed_at"):
            if run.started_at and run.completed_at:
                durations.append((run.completed_at - run.started_at).total_seconds())
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

        cat_meta_qs = period_meta_qs.filter(category=category)
        skip_breakdown = {
            reason: cat_meta_qs.filter(was_skipped=True, skip_reason=reason).count()
            for reason in skip_values
        }

        by_source = (
            cat_meta_qs.filter(was_skipped=True)
            .values("source_name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        skip_by_source = [
            {"source": item["source_name"] or "Unknown", "count": int(item["count"])}
            for item in by_source
        ]

        source_health = []
        for source in ScrapingSourceHealth.objects.filter(category=category).order_by(
            "source_name"
        ):
            source_health.append(
                {
                    "source": source.source_name,
                    "state": source.circuit_state,
                    "score": round(float(source.health_score or 0) / 100.0, 4),
                }
            )

        # Keep Source Health charts populated even when health snapshots are missing
        # by backfilling active sources with a neutral default score.
        existing_health_sources = {
            str(item.get("source") or "").strip().lower() for item in source_health
        }
        for source in ScrapingSource.objects.filter(
            category=category, is_active=True
        ).only("name"):
            source_name = str(source.name or "").strip()
            if not source_name:
                continue
            if source_name.lower() in existing_health_sources:
                continue
            source_health.append(
                {
                    "source": source_name,
                    "state": "unknown",
                    "score": 0.0,
                }
            )

        last_completed = completed_runs.aggregate(last_run_at=Max("started_at"))[
            "last_run_at"
        ]

        category_label = str(
            _(CATEGORY_META.get(category, {}).get("label", category.title()))
        )
        approval_rate = 0.0
        approved_records = 0
        total_records = 0

        cfg = category_cfg_map.get(category)
        if cfg is not None:
            model_cls = cfg.get("model")
            source_field = cfg.get("source_field")
            status_field = cfg.get("status_field")
            date_field = cfg.get("date_field")
            if model_cls and source_field and status_field and date_field:
                field_names = {
                    field.name
                    for field in model_cls._meta.get_fields()
                    if getattr(field, "concrete", False)
                }
                cat_qs = model_cls.objects.all()
                if source_field in field_names:
                    cat_qs = cat_qs.exclude(
                        **{f"{source_field}__isnull": True}
                    ).exclude(**{source_field: ""})
                cat_qs = _apply_date_window(cat_qs, date_field, window)

                total_records = cat_qs.count()
                approved_records = cat_qs.filter(**{status_field: "approved"}).count()
                approval_rate = round(
                    _safe_percentage(approved_records, total_records), 1
                )

        approval_by_category.append(
            {
                "category": category,
                "label": category_label,
                "approved": int(approved_records),
                "total": int(total_records),
                "approval_rate": float(approval_rate),
                "color": _source_color_token(category),
            }
        )

        by_category[category] = {
            "total_runs": int(total_runs),
            "total_saved": int(total_saved),
            "total_skipped": int(total_skipped),
            "skip_breakdown": skip_breakdown,
            "skip_by_source": skip_by_source,
            "avg_run_duration_seconds": float(avg_duration),
            "last_run_at": last_completed.isoformat() if last_completed else None,
            "source_health": source_health,
            "approval_rate": float(approval_rate),
            "approved": int(approved_records),
            "total_records": int(total_records),
        }

    approval_by_category.sort(key=lambda item: item["approval_rate"], reverse=True)

    date_points = [
        window["start_date"] + timedelta(days=idx) for idx in range(window["days"])
    ]
    date_to_index = {date_value: idx for idx, date_value in enumerate(date_points)}
    category_series = {category: [0] * len(date_points) for category in category_keys}

    # Build the daily scraped volume from persisted category records.
    # This keeps analytics useful even when run logs are incomplete or rotated.
    for category in category_keys:
        cfg = category_cfg_map.get(category) or {}
        model_cls = cfg.get("model")
        date_field = cfg.get("date_field")
        source_field = cfg.get("source_field")
        if not model_cls or not date_field:
            continue

        field_names = {
            field.name
            for field in model_cls._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        if date_field not in field_names:
            continue

        records_qs = model_cls.objects.all()
        if source_field and source_field in field_names:
            records_qs = records_qs.exclude(
                **{f"{source_field}__isnull": True}
            ).exclude(**{source_field: ""})
        records_qs = _apply_date_window(records_qs, date_field, window)

        grouped = records_qs.values(f"{date_field}__date").annotate(total=Count("id"))
        date_key = f"{date_field}__date"
        for row in grouped:
            row_date = row.get(date_key)
            if row_date in date_to_index:
                category_series[category][date_to_index[row_date]] += int(
                    row.get("total") or 0
                )

    series_runs = _apply_date_window(
        ScrapingRun.objects.filter(status="completed"),
        "started_at",
        window,
    ).only("category", "started_at", "items_found", "items_created", "items_skipped")

    for run in series_runs:
        run_date = run.started_at.date() if run.started_at else None
        if run_date is None or run_date not in date_to_index:
            continue
        if run.category not in category_series:
            continue
        if category_series[run.category][date_to_index[run_date]] == 0:
            category_series[run.category][date_to_index[run_date]] += (
                _run_items_scraped_count(run)
            )

    translated_count = period_meta_qs.filter(translation_status="translated").count()
    copied_count = period_meta_qs.filter(
        translation_status__in=["copied", "partial"]
    ).count()
    missing_count = period_meta_qs.filter(
        translation_status__in=["missing", "pending"]
    ).count()
    fully_translated_pct = round(
        _safe_percentage(translated_count, period_meta_qs.count()),
        1,
    )

    rejection_reasons_order = [
        ("irrelevant", str(_("Irrelevant"))),
        ("poor_arabic", str(_("Poor Arabic"))),
        ("duplicate", str(_("Duplicate"))),
        ("bad_source", str(_("Bad source"))),
        ("other", str(_("Other"))),
    ]
    rejection_matrix = {
        key: {category: 0 for category in category_keys}
        for key, _label in rejection_reasons_order
    }

    rejected_qs = RejectedItem.objects.filter(
        created_at__date__gte=window["start_date"],
        created_at__date__lte=window["end_date"],
    )
    for rejected_item in rejected_qs.only("category", "reason_for_rejection"):
        category = str(rejected_item.category or "").strip().lower()
        if category not in rejection_matrix["other"]:
            continue
        reason_key = _normalize_rejection_reason(rejected_item.reason_for_rejection)
        rejection_matrix[reason_key][category] += 1

    rejection_reasons = {
        "categories": category_keys,
        "datasets": [
            {
                "key": key,
                "label": label,
                "values": [
                    int(rejection_matrix[key][category]) for category in category_keys
                ],
            }
            for key, label in rejection_reasons_order
        ],
    }

    source_performance = []
    source_health_map = {}
    for source_health in ScrapingSourceHealth.objects.all():
        source_health_map[
            (source_health.category, source_health.source_name.lower())
        ] = source_health

    for source in ScrapingSource.objects.filter(is_active=True):
        source_runs = _apply_date_window(
            ScrapingRun.objects.filter(source=source),
            "started_at",
            window,
        )
        run_count = source_runs.count()
        if run_count == 0:
            continue

        completed_source_runs = source_runs.filter(status="completed")
        completed_count = completed_source_runs.count()
        items_created_total = int(
            completed_source_runs.aggregate(total=Sum("items_created"))["total"] or 0
        )
        avg_yield = (
            round(items_created_total / completed_count, 1) if completed_count else 0.0
        )

        source_meta = period_meta_qs.filter(source_name__iexact=source.name)
        accepted_count = source_meta.filter(was_skipped=False).count()
        skipped_count = source_meta.filter(was_skipped=True).count()
        approval_rate = round(
            _safe_percentage(accepted_count, accepted_count + skipped_count),
            1,
        )

        domain = urlparse(source.url or source.base_url or "").netloc
        health = source_health_map.get((source.category, source.name.lower()))
        health_score = int(round(float(getattr(health, "health_score", 0) or 0)))
        if health_score >= 80:
            health_state = "good"
        elif health_score >= 50:
            health_state = "warn"
        else:
            health_state = "bad"

        source_performance.append(
            {
                "id": str(source.id),
                "name": source.name,
                "domain": domain,
                "category": source.category,
                "runs": int(run_count),
                "avg_yield": float(avg_yield),
                "approval_rate": float(approval_rate),
                "health_score": int(health_score),
                "health_state": health_state,
            }
        )

    source_performance.sort(
        key=lambda row: (-row["runs"], -row["approval_rate"], -row["avg_yield"])  # noqa: E501
    )
    source_performance = source_performance[:12]

    duplicate_qs = period_meta_qs.filter(
        was_skipped=True, skip_reason__startswith="dedup_"
    )
    duplicate_by_category = {category: 0 for category in category_keys}
    for row in duplicate_qs.values("category").annotate(count=Count("id")):
        category = str(row.get("category") or "").strip().lower()
        if category in duplicate_by_category:
            duplicate_by_category[category] = int(row.get("count") or 0)

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
        _file_counts(
            Course.objects.all(), image_field="thumbnail", pdf_field="uploaded_file"
        ),
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

    return {
        "window": {
            "range": window["range"],
            "label": window["range_label"],
            "start_date": window["start_date"].isoformat(),
            "end_date": window["end_date"].isoformat(),
            "days": int(window["days"]),
        },
        "kpis": kpis,
        "by_category": by_category,
        "media": {
            "total_images": total_images,
            "total_pdfs": total_pdfs,
            "storage_bytes": storage_bytes,
        },
        "enrichment": enrichment,
        "timeseries": {
            "dates": [value.isoformat() for value in date_points],
            "categories": category_series,
        },
        "approval_by_category": approval_by_category,
        "translation_quality": {
            "translated": int(translated_count),
            "copied": int(copied_count),
            "missing": int(missing_count),
            "total": int(period_meta_qs.count()),
            "fully_translated_pct": float(fully_translated_pct),
        },
        "rejection_reasons": rejection_reasons,
        "source_performance": source_performance,
        "duplicates_summary": {
            "total": int(duplicate_qs.count()),
            "by_category": duplicate_by_category,
        },
    }


def _analytics_json_response(request, *, window=None):
    date_window = window or _parse_analytics_date_window(request)
    payload = _collect_analytics_payload(date_window)
    return JsonResponse(payload)


def _export_analytics_csv(payload: dict) -> HttpResponse:
    window_payload = payload.get("window") or {}
    filename = (
        f"scraping_analytics_{window_payload.get('start_date', 'start')}_"
        f"{window_payload.get('end_date', 'end')}.csv"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(
        ["Section", "Metric", "Value", "Change %", "Direction", "Improving"]
    )

    for metric_key, metric_payload in (payload.get("kpis") or {}).items():
        writer.writerow(
            [
                "KPI",
                metric_key,
                metric_payload.get("value", 0),
                metric_payload.get("change_pct", 0),
                metric_payload.get("direction", "flat"),
                "yes" if metric_payload.get("improving") else "no",
            ]
        )

    writer.writerow([])
    writer.writerow(["Time Series"])
    dates = (payload.get("timeseries") or {}).get("dates") or []
    series = (payload.get("timeseries") or {}).get("categories") or {}
    category_headers = list(series.keys())
    writer.writerow(["Date", *category_headers])
    for index, date_value in enumerate(dates):
        writer.writerow(
            [
                date_value,
                *[
                    series.get(category, [0] * len(dates))[index]
                    for category in category_headers
                ],
            ]
        )

    writer.writerow([])
    writer.writerow(["Approval By Category"])
    writer.writerow(["Category", "Approved", "Total", "Approval Rate"])
    for row in payload.get("approval_by_category") or []:
        writer.writerow(
            [
                row.get("category"),
                row.get("approved"),
                row.get("total"),
                row.get("approval_rate"),
            ]
        )

    writer.writerow([])
    writer.writerow(["Translation Quality"])
    translation = payload.get("translation_quality") or {}
    writer.writerow(["translated", translation.get("translated", 0)])
    writer.writerow(["copied", translation.get("copied", 0)])
    writer.writerow(["missing", translation.get("missing", 0)])
    writer.writerow(
        ["fully_translated_pct", translation.get("fully_translated_pct", 0)]
    )

    writer.writerow([])
    writer.writerow(["Source Performance"])
    writer.writerow(["Source", "Category", "Runs", "Avg Yield", "Approval", "Health"])
    for row in payload.get("source_performance") or []:
        writer.writerow(
            [
                row.get("name"),
                row.get("category"),
                row.get("runs"),
                row.get("avg_yield"),
                row.get("approval_rate"),
                row.get("health_score"),
            ]
        )

    writer.writerow([])
    writer.writerow(["Duplicates"])
    duplicates_summary = payload.get("duplicates_summary") or {}
    writer.writerow(["total", duplicates_summary.get("total", 0)])
    for category, count in (duplicates_summary.get("by_category") or {}).items():
        writer.writerow([category, count])

    return response


@login_required
@staff_member_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def trends(request):
    """Return trend datasets used by the analytics dashboard charts."""
    _log_scraping_action(request)
    window = _parse_analytics_date_window(request)

    payload = _collect_analytics_payload(window)
    months = max(1, min(24, int(round(window["days"] / 30.0)) or 1))

    try:
        legacy = detect_trends(months=months)
    except Exception as exc:
        logger.exception("Trend detection failed: %s", exc)
        legacy = {"status": "error", "message": str(exc)}

    if not isinstance(legacy, dict):
        legacy = {"status": "ok", "legacy_data": legacy}

    legacy_payload = {
        key: value for key, value in legacy.items() if key not in {"status"}
    }

    return JsonResponse(
        {
            "status": "ok",
            "window": payload.get("window"),
            "timeseries": payload.get("timeseries"),
            "approval_by_category": payload.get("approval_by_category"),
            "translation_quality": payload.get("translation_quality"),
            "rejection_reasons": payload.get("rejection_reasons"),
            "source_performance": payload.get("source_performance"),
            "kpis": payload.get("kpis"),
            "legacy_status": legacy.get("status", "ok"),
            **legacy_payload,
        }
    )


@login_required
@staff_member_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=30, period_seconds=60, scope="analytics")
def analytics(request):
    """Structured scraping analytics payload used by charts and exports."""
    _log_scraping_action(request)
    return _analytics_json_response(request)


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
    """Return duplicate preview for a category, or summary when no category is provided."""
    _log_scraping_action(request)
    category = (request.GET.get("category") or "").strip().lower()
    window = _parse_analytics_date_window(request)

    if not category:
        duplicates_qs = ScrapedItemMeta.objects.filter(
            was_skipped=True,
            skip_reason__startswith="dedup_",
            created_at__date__gte=window["start_date"],
            created_at__date__lte=window["end_date"],
        )
        by_category = {key: 0 for key in CATEGORY_META}
        for row in duplicates_qs.values("category").annotate(count=Count("id")):
            key = str(row.get("category") or "").strip().lower()
            if key in by_category:
                by_category[key] = int(row.get("count") or 0)

        top_sources = [
            {"source": row["source_name"] or "Unknown", "count": int(row["count"])}
            for row in duplicates_qs.values("source_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:12]
        ]

        return JsonResponse(
            {
                "window": {
                    "range": window["range"],
                    "start_date": window["start_date"].isoformat(),
                    "end_date": window["end_date"].isoformat(),
                },
                "total_duplicates": int(duplicates_qs.count()),
                "by_category": by_category,
                "top_sources": top_sources,
            }
        )

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
    if category == "courses":
        return {
            "title_en": title,
            "description_en": description,
            "access_link": item_url,
            "instructor": item.get("instructor") or "",
        }
    return {"title_en": title}


@login_required
@user_passes_test(is_admin)
@csrf_protect
@require_http_methods(["GET", "POST"])
def scraping_sources_page(request):
    """Render and manage trusted scraping sources used by the research pipeline."""
    _log_scraping_action(request)

    if request.method == "POST":
        content_type_error = _require_json_content_type(request)
        if content_type_error:
            return content_type_error

        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": _("Invalid JSON payload")}, status=400)

        source, created, error = _save_source_payload(payload)
        if source is None:
            return JsonResponse(
                {"error": error or _("Unable to save source")}, status=400
            )

        row = _build_source_row_payload(source)
        return JsonResponse(
            {
                "success": True,
                "created": created,
                "source": {
                    "id": row["id"],
                    "name": row["name"],
                    "url": row["url"],
                    "category": row["category"],
                    "is_active": row["is_active"],
                },
            }
        )

    _ensure_default_scraping_sources()

    resolver_url_name = ""
    route_category = ""
    if request.resolver_match is not None:
        resolver_url_name = str(request.resolver_match.url_name or "")
        route_category = (
            str((request.resolver_match.kwargs or {}).get("category") or "")
            .strip()
            .lower()
        )

    category_scope = None
    if route_category in SCRAPING_NAV_CATEGORY_KEYS:
        category_scope = route_category
    elif (
        getattr(request, "_scraping_category", "")
        or resolver_url_name == "category_sources"
    ):
        category_scope = _resolve_scraping_nav_category(request)

    sources_queryset = ScrapingSource.objects.all()
    if category_scope:
        sources_queryset = sources_queryset.filter(category=category_scope)

    sources = list(sources_queryset.order_by("category", "name"))
    rows = [_build_source_row_payload(source) for source in sources]

    active_sources = [row for row in rows if row["is_active"]]
    failing_sources = [row for row in rows if row["failing"]]
    disabled_sources = [row for row in rows if not row["is_active"]]

    latest_check = None
    for row in rows:
        candidate = row.get("last_checked_at")
        if candidate is None:
            continue
        if latest_check is None or candidate > latest_check:
            latest_check = candidate

    fixture_payload = _load_arabic_nlp_fixture_payload()
    existing_url_set = {
        (str(source.url or source.base_url or "").strip().lower()) for source in sources
    }
    existing_name_set = {str(source.name or "").strip().lower() for source in sources}

    suggested_sources_by_category = defaultdict(list)
    for raw in fixture_payload.get("sources", []):
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "").strip().lower()
        if category not in CATEGORY_META:
            continue

        url = str(raw.get("url") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not url or not name:
            continue

        if url.lower() in existing_url_set or name.lower() in existing_name_set:
            continue

        try:
            trust_score = round(float(raw.get("trust_score", 0.8)), 2)
        except (TypeError, ValueError):
            trust_score = 0.8

        try:
            priority = int(raw.get("priority", 3) or 3)
        except (TypeError, ValueError):
            priority = 3

        queries = (
            raw.get("search_queries")
            if isinstance(raw.get("search_queries"), list)
            else []
        )
        cleaned_queries = [
            str(value).strip() for value in queries if str(value).strip()
        ]
        suggested_sources_by_category[category].append(
            {
                "name": name,
                "url": url,
                "category": category,
                "trust_score": trust_score,
                "priority": priority,
                "queries": cleaned_queries,
            }
        )

    query_templates = fixture_payload.get("query_templates", {})
    query_suggestions = {
        key: [
            str(value).strip()
            for value in (query_templates.get(key) or [])
            if str(value).strip()
        ][:3]
        for key in CATEGORY_META
    }

    category_options = [
        {
            "key": key,
            "label": CATEGORY_META.get(key, {}).get("label", key.title()),
            "color": _source_color_token(key),
        }
        for key in CATEGORY_META
    ]

    context = {
        "sources_rows": rows,
        "sources_default_category": category_scope or "all",
        "category_options": category_options,
        "active_sources_count": len(active_sources),
        "failing_sources_count": len(failing_sources),
        "disabled_sources_count": len(disabled_sources),
        "latest_check": latest_check,
        "suggested_sources_by_category": dict(suggested_sources_by_category),
        "query_suggestions": query_suggestions,
        "page": "scraping",
        **_scraping_shell_context(request, active_page="sources"),
    }

    return render(request, "scraping/sources.html", context)


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=20, period_seconds=60, scope="action")
def test_source_connection(request):
    """Run URL-level network/content checks before saving a new source."""
    _log_scraping_action(request)

    content_type_error = _require_json_content_type(request)
    if content_type_error:
        return content_type_error

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Invalid JSON payload")}, status=400)

    url = str(payload.get("url") or "").strip()
    category = str(payload.get("category") or "events").strip().lower()
    if not url:
        return JsonResponse({"error": _("Source URL is required.")}, status=400)
    if category not in CATEGORY_META:
        category = "events"

    network = NetworkValidator(url).run()
    content = None
    if network.get("overall") != "RED":
        content = ContentValidator(url, category).run()

    robots = network.get("robots") if isinstance(network.get("robots"), dict) else {}
    robots_status = str(robots.get("status") or "NO_ROBOTS_FILE")

    if network.get("overall") == "RED":
        status = "failed"
    elif robots_status == "DISALLOWED":
        status = "warning"
    else:
        status = "success"

    estimated_yield = 0
    if content:
        verdict = str(content.get("verdict") or "").upper()
        keyword_score = int(content.get("keyword_score") or 0)
        if verdict == "RELEVANT":
            estimated_yield = max(8, 8 + int(keyword_score / 8))
        elif verdict == "UNCERTAIN":
            estimated_yield = max(3, 3 + int(keyword_score / 20))

    return JsonResponse(
        {
            "status": status,
            "network": network,
            "content": content,
            "robots_status": robots_status,
            "estimated_yield": estimated_yield,
        }
    )


@login_required
@user_passes_test(is_admin)
@require_GET
@rate_limit(max_calls=60, period_seconds=60, scope="polling")
def source_health_detail(request, source_id):
    """Return per-source health summary and mini-series used by table hovers."""
    _log_scraping_action(request)
    source = ScrapingSource.objects.filter(pk=source_id).first()
    if source is None:
        return JsonResponse({"error": _("Source not found")}, status=404)

    row = _build_source_row_payload(source)
    return JsonResponse(
        {
            "id": row["id"],
            "name": row["name"],
            "success_rate": row["success_rate"],
            "consecutive_failures": row["consecutive_failures"],
            "avg_yield": row["avg_yield"],
            "health_points": row["health_points"],
            "last_run_iso": row["last_run_iso"],
            "last_checked_iso": row["last_checked_iso"],
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=30, period_seconds=60, scope="action")
def toggle_custom_source(request, source_id):
    """Toggle source active state for quarantine/disable workflows."""
    _log_scraping_action(request)

    source = ScrapingSource.objects.filter(pk=source_id).first()
    if source is None:
        return JsonResponse({"error": _("Source not found")}, status=404)

    is_active = None
    if request.content_type and "application/json" in request.content_type.lower():
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            payload = {}
        if "is_active" in payload:
            is_active = _as_bool(payload.get("is_active"), default=source.is_active)

    if is_active is None:
        is_active = not source.is_active

    source.is_active = bool(is_active)
    source.is_admin_disabled = not source.is_active
    source.save(update_fields=["is_active", "is_admin_disabled"])

    return JsonResponse(
        {
            "success": True,
            "id": str(source.id),
            "is_active": bool(source.is_active),
            "message": "Source activated" if source.is_active else "Source disabled",
        }
    )


@login_required
@user_passes_test(is_admin)
@require_POST
@csrf_protect
@rate_limit(max_calls=60, period_seconds=60, scope="action")
def update_source_settings(request, source_id):
    """Update editable source settings from the settings page."""
    _log_scraping_action(request)

    source = ScrapingSource.objects.filter(pk=source_id).first()
    if source is None:
        return JsonResponse({"error": _("Source not found")}, status=404)

    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, json.JSONDecodeError):
        payload = request.POST

    schedule_tier = str(payload.get("schedule_tier") or source.schedule_tier).strip()
    allowed_tiers = {"very_high", "high", "medium", "low", "dormant"}
    if schedule_tier not in allowed_tiers:
        return JsonResponse({"error": _("Invalid schedule tier")}, status=400)

    interval_hours_raw = payload.get(
        "schedule_interval_hours", source.schedule_interval_hours
    )
    try:
        interval_hours = int(interval_hours_raw)
    except (TypeError, ValueError):
        return JsonResponse({"error": _("Invalid schedule interval")}, status=400)

    if interval_hours < 1 or interval_hours > 168:
        return JsonResponse(
            {"error": _("Schedule interval must be between 1 and 168 hours")},
            status=400,
        )

    source.is_active = _as_bool(payload.get("is_active"), default=source.is_active)
    source.is_admin_disabled = not source.is_active
    source.use_rss = _as_bool(payload.get("use_rss"), default=source.use_rss)
    source.use_llm_extraction = _as_bool(
        payload.get("use_llm_extraction"),
        default=source.use_llm_extraction,
    )
    source.verify_ssl = _as_bool(payload.get("verify_ssl"), default=source.verify_ssl)
    source.schedule_tier = schedule_tier
    source.schedule_interval_hours = interval_hours
    source.schedule_updated_at = timezone.now()

    source.save(
        update_fields=[
            "is_active",
            "is_admin_disabled",
            "use_rss",
            "use_llm_extraction",
            "verify_ssl",
            "schedule_tier",
            "schedule_interval_hours",
            "schedule_updated_at",
        ]
    )

    return JsonResponse(
        {
            "success": True,
            "id": str(source.id),
            "is_active": bool(source.is_active),
            "use_rss": bool(source.use_rss),
            "use_llm_extraction": bool(source.use_llm_extraction),
            "verify_ssl": bool(source.verify_ssl),
            "schedule_tier": source.schedule_tier,
            "schedule_interval_hours": int(source.schedule_interval_hours),
        }
    )


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
                "courses": scraper._dedup_course,
            }
            checker = checker_map.get(category)
            if checker is not None:
                duplicate, reason, _score = checker(mapped)

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

    if not _check_rate_limit(request, scope="test_source", max_calls=20, period=3600):
        return JsonResponse(
            {"error": "Too many source test requests."},
            status=429,
            headers={"Retry-After": "3600"},
        )

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
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Invalid JSON payload")}, status=400)

    if not data.get("category"):
        url = str(data.get("url") or "").strip()
        detected_category = CustomDomainScraper.detect_category_from_signals(url, "")
        if detected_category not in CATEGORY_META:
            detected_category = "events"
        data["category"] = detected_category
        scrape_config = (
            data.get("scrape_config")
            if isinstance(data.get("scrape_config"), dict)
            else {}
        )
        scrape_config["auto_detect_category"] = True
        scrape_config["detected_from_url"] = True
        data["scrape_config"] = scrape_config

    source, created, error = _save_source_payload(data)
    if source is None:
        return JsonResponse({"error": error or _("Unable to save source")}, status=400)

    return JsonResponse(
        {
            "success": True,
            "created": created,
            "id": str(source.id),
            "name": source.name,
            "category": source.category,
            "is_active": source.is_active,
        }
    )


@login_required
@require_http_methods(["POST", "DELETE"])
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

    sources = ScrapingSource.objects.all().order_by("-created_at")
    data = [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.url or s.base_url,
            "category": s.category,
            "is_active": bool(s.is_active),
            "trust_score": _extract_scrape_config_value(s, "trust_score", 0.8),
            "priority": _extract_scrape_config_value(s, "priority", 3),
            "search_queries": _extract_scrape_config_value(s, "search_queries", []),
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
    if generate_latest is None:
        return JsonResponse(
            {"error": "Metrics endpoint disabled: prometheus_client not installed."},
            status=503,
        )

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
    """Prometheus metrics endpoint restricted to authenticated staff users."""
    _log_scraping_action(request)

    if not request.user.is_authenticated or not bool(
        getattr(request.user, "is_staff", False)
    ):
        return JsonResponse({"error": "forbidden"}, status=403)

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
