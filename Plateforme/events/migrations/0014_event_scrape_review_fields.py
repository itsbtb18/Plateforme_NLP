from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0013_event_scrape_tracking_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="scrape_status",
            field=models.CharField(
                choices=[
                    ("APPROVED", "Approved"),
                    ("PENDING_REVIEW", "Pending review"),
                    ("REJECTED", "Rejected"),
                ],
                db_index=True,
                default="PENDING_REVIEW",
                max_length=20,
                verbose_name="Scrape Status",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="validation_notes",
            field=models.TextField(blank=True, default="", verbose_name="Validation Notes"),
        ),
        migrations.AddField(
            model_name="event",
            name="confidence_score",
            field=models.FloatField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Confidence Score",
            ),
        ),
    ]
