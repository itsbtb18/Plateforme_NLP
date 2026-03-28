from django.db import migrations, models


def backfill_url_from_base_url(apps, schema_editor):
    ScrapingSource = apps.get_model("scraping", "ScrapingSource")
    for source in ScrapingSource.objects.all().iterator():
        if not source.url and source.base_url:
            source.url = source.base_url
            source.save(update_fields=["url"])


class Migration(migrations.Migration):

    dependencies = [
        ("scraping", "0015_scrapingsource_quarantine_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="source_type",
            field=models.CharField(
                choices=[("web", "Web scraping"), ("api", "API")],
                default="web",
                max_length=20,
                verbose_name="Source Type",
            ),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="url",
            field=models.URLField(blank=True, default="", verbose_name="URL"),
        ),
        migrations.RunPython(backfill_url_from_base_url, migrations.RunPython.noop),
    ]
