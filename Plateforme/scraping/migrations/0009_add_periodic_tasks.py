import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def create_periodic_tasks(apps, schema_editor):
    try:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule

        # Daily at 4am — News
        daily_4am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="4",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )

        # Weekly Monday at 2am — Events
        weekly_mon_2am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="2",
            day_of_week="1",
            day_of_month="*",
            month_of_year="*",
        )

        # Weekly Monday at 3am — Tools
        weekly_mon_3am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="3",
            day_of_week="1",
            day_of_month="*",
            month_of_year="*",
        )

        # Monthly 1st at 5am — Courses
        monthly_5am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="5",
            day_of_week="*",
            day_of_month="1",
            month_of_year="*",
        )

        # Monthly 1st at 6am — Institutions
        monthly_6am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="6",
            day_of_week="*",
            day_of_month="1",
            month_of_year="*",
        )

        tasks_to_create = [
            {
                "name": "Auto-scrape News Daily",
                "task": "scraping.tasks.run_scraper_task",
                "crontab": daily_4am,
                "args": '["news"]',
            },
            {
                "name": "Auto-scrape Events Weekly",
                "task": "scraping.tasks.run_scraper_task",
                "crontab": weekly_mon_2am,
                "args": '["events"]',
            },
            {
                "name": "Auto-scrape Tools Weekly",
                "task": "scraping.tasks.run_scraper_task",
                "crontab": weekly_mon_3am,
                "args": '["tools"]',
            },
            {
                "name": "Auto-scrape Courses Monthly",
                "task": "scraping.tasks.run_scraper_task",
                "crontab": monthly_5am,
                "args": '["courses"]',
            },
            {
                "name": "Auto-scrape Institutions Monthly",
                "task": "scraping.tasks.run_scraper_task",
                "crontab": monthly_6am,
                "args": '["institutions"]',
            },
        ]

        for task_config in tasks_to_create:
            task, _ = PeriodicTask.objects.get_or_create(
                name=task_config["name"],
                defaults={
                    "task": task_config["task"],
                    "crontab": task_config["crontab"],
                    "args": task_config["args"],
                    "enabled": True,
                },
            )

            # Keep existing records in sync without creating duplicates.
            changed = False
            if task.task != task_config["task"]:
                task.task = task_config["task"]
                changed = True
            if task.crontab_id != task_config["crontab"].id:
                task.crontab = task_config["crontab"]
                changed = True
            if (task.args or "") != task_config["args"]:
                task.args = task_config["args"]
                changed = True
            if not task.enabled:
                task.enabled = True
                changed = True
            if changed:
                task.save(update_fields=["task", "crontab", "args", "enabled"])

        print(f"Created {len(tasks_to_create)} periodic scraping tasks.")

    except Exception as e:
        print(f"Could not create periodic tasks: {e}")
        print("Run manually via Django admin.")


def remove_periodic_tasks(apps, schema_editor):
    try:
        from django_celery_beat.models import PeriodicTask

        PeriodicTask.objects.filter(task="scraping.tasks.run_scraper_task").delete()
    except Exception as exc:
        logger.warning(
            "periodic_task_cleanup_failed",
            extra={"error": str(exc), "context": "scraping.tasks.run_scraper_task"},
            exc_info=False,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0008_alter_scrapingsource_last_run_status"),
    ]

    operations = [
        migrations.RunPython(create_periodic_tasks, remove_periodic_tasks),
    ]
