"""
Celery tasks for the Web Scraping module.

Provides background execution of scrapers so the admin dashboard
returns immediately while scraping runs asynchronously.
"""

import logging
from celery import shared_task
from django.utils import timezone

from .scrapers import get_scraper, CATEGORY_META

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

        logger.info(
            "Scraper %s completed: %d created, %d skipped",
            category, run.items_created, run.items_skipped,
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
        logger.exception("Scraper %s failed", category)
        raise  # Re-raise so Celery marks the task as FAILURE
