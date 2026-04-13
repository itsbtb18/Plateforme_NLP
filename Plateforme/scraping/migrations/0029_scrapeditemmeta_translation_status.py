from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0028_scrapingrun_progress_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapeditemmeta",
            name="translation_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("translated", "Translated"),
                    ("failed", "Failed"),
                    ("partial", "Partial"),
                ],
                db_index=True,
                default="pending",
                help_text="Arabic translation pipeline status for this item.",
                max_length=12,
                verbose_name="Translation Status",
            ),
        ),
    ]
