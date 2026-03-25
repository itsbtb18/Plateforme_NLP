from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0012_scrapeditemmeta_skip_reason_choices_and_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="download_result",
            field=models.CharField(
                blank=True,
                help_text="DownloadResult code for the media download attempt",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="match_score",
            field=models.FloatField(
                blank=True,
                help_text="Similarity score when item was dedup-skipped (0.0-1.0)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="matched_item_id",
            field=models.CharField(
                blank=True,
                help_text="ID of the existing DB item this was matched against",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="source_name",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Human label of source e.g. WikiCFP, arXiv cs.CL",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="Canonical URL of the source page or feed",
                max_length=2000,
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="scrapeditemmeta",
            index=models.Index(
                fields=["category", "source_name"], name="idx_scraped_cat_source"
            ),
        ),
        migrations.AddIndex(
            model_name="scrapeditemmeta",
            index=models.Index(
                fields=["category", "skip_reason", "created_at"],
                name="idx_scraped_cat_skip_created",
            ),
        ),
    ]
