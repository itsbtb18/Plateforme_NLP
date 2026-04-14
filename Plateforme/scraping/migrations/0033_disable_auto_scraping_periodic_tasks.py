import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def disable_auto_scraping_periodic_tasks(apps, schema_editor):
    try:
        from django_celery_beat.models import PeriodicTask
    except Exception as exc:
        logger.warning("django_celery_beat_unavailable", extra={"error": str(exc)})
        return

    PeriodicTask.objects.filter(
        task__in=[
            "scraping.tasks.run_scraper_task",
            "scraping.tasks.update_adaptive_schedules",
        ]
    ).update(enabled=False)

    PeriodicTask.objects.filter(name__startswith="scraping_").update(enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0032_create_rejecteditem_model"),
    ]

    operations = [
        migrations.RunPython(disable_auto_scraping_periodic_tasks, migrations.RunPython.noop),
    ]
