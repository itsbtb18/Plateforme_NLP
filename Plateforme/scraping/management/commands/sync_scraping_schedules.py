from django.core.management.base import BaseCommand

from scraping.schedule_config import SCRAPING_SCHEDULES


class Command(BaseCommand):
    help = "Sync scraping periodic schedules into django-celery-beat tables."

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(f"django-celery-beat unavailable: {exc}")
            )
            return

        created_count = 0
        updated_count = 0

        for config in SCRAPING_SCHEDULES:
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=config["minute"],
                hour=config["hour"],
                day_of_week=config["day_of_week"],
                day_of_month=config["day_of_month"],
                month_of_year=config["month_of_year"],
            )

            task, created = PeriodicTask.objects.get_or_create(
                name=config["name"],
                defaults={
                    "task": config["task"],
                    "crontab": crontab,
                    "args": config["args"],
                    "enabled": config.get("enabled", True),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"created: {task.name}"))
                continue

            changed = False
            if task.task != config["task"]:
                task.task = config["task"]
                changed = True
            if task.crontab_id != crontab.id:
                task.crontab = crontab
                changed = True
            if (task.args or "") != config["args"]:
                task.args = config["args"]
                changed = True
            desired_enabled = config.get("enabled", True)
            if task.enabled != desired_enabled:
                task.enabled = desired_enabled
                changed = True

            if changed:
                task.save(update_fields=["task", "crontab", "args", "enabled"])
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"updated: {task.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"sync complete created={created_count} updated={updated_count} total={len(SCRAPING_SCHEDULES)}"
            )
        )
