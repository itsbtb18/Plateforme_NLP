from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0010_scrapeditemmeta_skip_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="enrichment_status",
            field=models.CharField(
                choices=[
                    ("not_enriched", "Not Enriched"),
                    ("partial", "Partial"),
                    ("complete", "Complete"),
                ],
                default="not_enriched",
                help_text="Whether deep enrichment fully succeeded for this item.",
                max_length=20,
                verbose_name="Enrichment Status",
            ),
        ),
    ]
