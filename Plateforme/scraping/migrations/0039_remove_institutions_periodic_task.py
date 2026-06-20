from django.db import migrations


def remove_institutions_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

        deleted_by_name, _ = PeriodicTask.objects.filter(
            name__icontains="institutions"
        ).delete()
        print(f"Removed {deleted_by_name} institutions periodic tasks by name")

        deleted_by_args, _ = PeriodicTask.objects.filter(
            task__icontains="scraping",
            args__icontains="institutions",
        ).delete()
        print(f"Removed {deleted_by_args} institutions periodic tasks by args")
    except Exception as exc:  # pragma: no cover - migration safety fallback
        print(f"Note: {exc}")


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0038_remove_scrapingsource_force_playwright_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_institutions_task,
            migrations.RunPython.noop,
        ),
    ]
