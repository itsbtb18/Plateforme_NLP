"""
Views for the Web Scraping module.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
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
    total_created = sum(r.items_created for r in ScrapingRun.objects.all())

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
    """AJAX endpoint: run a scraper for the given category."""
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
