from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0011_scrapeditemmeta_enrichment_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scrapeditemmeta",
            name="skip_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("dedup_url", "Dedup URL"),
                    ("dedup_name", "Dedup Name"),
                    ("dedup_similarity", "Dedup Similarity"),
                    ("dedup_embedding", "Dedup Embedding"),
                    ("dedup_doi", "Dedup DOI"),
                    ("dedup_arxiv", "Dedup arXiv"),
                    ("dedup_ror", "Dedup ROR"),
                    ("download_fail", "Download Failed"),
                    ("validation_fail", "Validation Failed"),
                    ("enrichment_fail", "Enrichment Failed"),
                    ("circuit_open", "Circuit Open"),
                ],
                help_text="Reason why this scraped candidate was skipped as duplicate.",
                max_length=32,
                null=True,
                verbose_name="Skip Reason",
            ),
        ),
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="was_skipped",
            field=models.BooleanField(
                default=False,
                help_text="Whether this candidate was skipped in ingestion.",
                verbose_name="Was Skipped",
            ),
        ),
    ]
