from django.db import migrations, models
from django.db.models import F


def backfill_current_message(apps, schema_editor):
    ScrapingRun = apps.get_model("scraping", "ScrapingRun")
    ScrapingRun.objects.filter(current_message="").update(current_message=F("current_step"))


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0034_scrapingrun_progress_tracking_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingrun",
            name="current_message",
            field=models.CharField(blank=True, max_length=255, verbose_name="Current Message"),
        ),
        migrations.RunPython(backfill_current_message, migrations.RunPython.noop),
    ]
