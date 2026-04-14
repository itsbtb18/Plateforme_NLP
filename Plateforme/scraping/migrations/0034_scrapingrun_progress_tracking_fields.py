from django.db import migrations, models
from django.db.models import F


def backfill_scraping_run_progress_fields(apps, schema_editor):
    ScrapingRun = apps.get_model("scraping", "ScrapingRun")
    ScrapingRun.objects.filter(items_failed=0).update(items_failed=F("items_skipped"))
    ScrapingRun.objects.filter(current_item="").update(current_item=F("current_source"))


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0034_enforce_manual_only_scraping"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingrun",
            name="current_item",
            field=models.CharField(blank=True, max_length=255, verbose_name="Current Item"),
        ),
        migrations.AddField(
            model_name="scrapingrun",
            name="items_failed",
            field=models.IntegerField(default=0, verbose_name="Items Failed"),
        ),
        migrations.RunPython(
            backfill_scraping_run_progress_fields,
            migrations.RunPython.noop,
        ),
    ]
