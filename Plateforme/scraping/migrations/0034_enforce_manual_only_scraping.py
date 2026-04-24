from django.db import migrations


def disable_all_scraping_periodic_tasks(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        # Disable all scraping-related periodic tasks
        disabled = PeriodicTask.objects.filter(
            task__icontains='scraping'
        ).update(enabled=False)
        print(f"Disabled {disabled} scraping periodic tasks")

        # Also disable adaptive scheduler tasks
        disabled2 = PeriodicTask.objects.filter(
            name__icontains='scraping'
        ).update(enabled=False)
        print(f"Disabled {disabled2} additional scraping tasks by name")

    except Exception as e:
        print(f"Note: {e} - celery beat tables may not exist, skipping")


def re_enable_scraping_periodic_tasks(apps, schema_editor):
    # Reverse migration - re-enable tasks
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        PeriodicTask.objects.filter(
            task__icontains='scraping'
        ).update(enabled=True)
    except Exception as e:
        print(f"Note: {e}")


class Migration(migrations.Migration):
    dependencies = [
        ('scraping', '0033_disable_auto_scraping_periodic_tasks'),
    ]

    operations = [
        migrations.RunPython(
            disable_all_scraping_periodic_tasks,
            re_enable_scraping_periodic_tasks,
        ),
    ]
