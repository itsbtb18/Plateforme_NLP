from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0040_discoveredurl"),
    ]

    operations = [
        migrations.AddField(
            model_name="discoveredurl",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AddIndex(
            model_name="discoveredurl",
            index=models.Index(
                fields=["category", "status", "priority_score"],
                name="idx_discoveredurl_pending_queue",
            ),
        ),
    ]