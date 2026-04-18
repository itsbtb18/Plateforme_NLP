from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0008_opportunity"),
    ]

    operations = [
        migrations.AddField(
            model_name="opportunity",
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
            ),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="validation_notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="confidence_score",
            field=models.FloatField(blank=True, db_index=True, null=True),
        ),
    ]
