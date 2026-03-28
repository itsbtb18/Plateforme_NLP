from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0020_scrapingsource_selector_discovery_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="content_source",
            field=models.CharField(
                choices=[
                    ("live", "Live"),
                    ("wayback", "Wayback Machine"),
                    ("cache", "Cache"),
                ],
                default="live",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="archived_snapshot_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]
