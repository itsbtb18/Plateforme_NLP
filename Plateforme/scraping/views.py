"""
Views for the Web Scraping module.

Supports both synchronous (fallback) and asynchronous (Celery) execution.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from .models import ScrapingRun
from .scrapers import get_scraper, get_all_categories, CATEGORY_META

logger = logging.getLogger(__name__)


def is_admin(user):
    """Check if user is an admin."""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin)
def dashboard(request):
    """Main scraping dashboard — staff only."""
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
    from django.db.models import Sum

    total_created = (
        ScrapingRun.objects.aggregate(total=Sum("items_created"))["total"] or 0
    )

    # Per-category item counts from actual models
    from events.models import Event
    from resources.models import NLPTool, Course
    from institutions.models import Institution
    from QA.models import Post

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

    return render(
        request,
        "scraping/dashboard.html",
        {
            "categories": categories,
            "total_runs": total_runs,
            "total_created": total_created,
            "model_counts": model_counts,
            "pending_counts": pending_counts,
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
        from .tasks import run_scraper_task

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
def task_status(request, run_id):
    """AJAX endpoint: poll the status of an asynchronous scraping run."""
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
                from celery.result import AsyncResult

                result = AsyncResult(run.task_id)
                if result.successful():
                    task_data = result.result or {}
                    results = task_data.get("results", [])
            except Exception:
                pass
        data.update({"errors": errors, "results": results})
    elif run.status == "failed":
        data["errors"] = run.errors.split("\n") if run.errors else []
        data["message"] = run.errors

    return JsonResponse(data)


@login_required
@require_POST
def run_custom_source(request, source_id):
    """AJAX endpoint: run the custom domain scraper for a single source."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    from scraping.models import ScrapingSource
    from scraping.scrapers.custom_scraper import CustomDomainScraper

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
def trends(request):
    """AJAX endpoint: return trend analysis for the last N months."""
    months = int(request.GET.get("months", 6))
    months = max(1, min(months, 24))  # clamp to 1-24

    try:
        from scraping.intelligence import detect_trends

        data = detect_trends(months=months)
        return JsonResponse({"status": "ok", **data})
    except Exception as exc:
        logger.exception("Trend detection failed: %s", exc)
        return JsonResponse(
            {"status": "error", "message": str(exc)},
            status=500,
        )


@login_required
@require_POST
def add_custom_source(request):
    """AJAX endpoint: add a new custom scraping source (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    import json

    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        url = data.get("url", "").strip()
        category = data.get("category", "events")
        use_rss = data.get("use_rss", True)
        use_llm = data.get("use_llm_extraction", True)

        if not name or not url:
            return JsonResponse({"error": "Name and URL are required"}, status=400)

        if not url.startswith(("http://", "https://")):
            return JsonResponse({"error": "Invalid URL format"}, status=400)

        from scraping.models import ScrapingSource

        source = ScrapingSource.objects.create(
            name=name,
            base_url=url,
            category=category,
            use_rss=use_rss,
            use_llm_extraction=use_llm,
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
def delete_custom_source(request, source_id):
    """AJAX endpoint: delete a custom scraping source (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    from scraping.models import ScrapingSource

    try:
        source = ScrapingSource.objects.get(id=source_id)
        name = source.name
        source.delete()
        return JsonResponse({"success": True, "name": name})
    except ScrapingSource.DoesNotExist:
        return JsonResponse({"error": "Source not found"}, status=404)


@login_required
def list_custom_sources(request):
    """AJAX endpoint: list all active custom scraping sources (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)
    from scraping.models import ScrapingSource

    sources = ScrapingSource.objects.filter(is_active=True).order_by("-created_at")
    data = [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.base_url,
            "category": s.category,
            "last_scraped": s.last_scraped.isoformat() if s.last_scraped else None,
            "last_run_status": s.last_run_status,
            "last_run_items_created": s.last_run_items_created,
        }
        for s in sources
    ]
    return JsonResponse({"sources": data})
