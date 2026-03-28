from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0021_scrapeditemmeta_content_source_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="schedule_interval_hours",
            field=models.IntegerField(default=24),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="schedule_tier",
            field=models.CharField(
                choices=[
                    ("very_high", "Very High"),
                    ("high", "High"),
                    ("medium", "Medium"),
                    ("low", "Low"),
                    ("dormant", "Dormant"),
                ],
                default="medium",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="schedule_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scrapingrun",
            name="source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="scraping_runs",
                to="scraping.scrapingsource",
                verbose_name="Source",
            ),
        ),
    ]
