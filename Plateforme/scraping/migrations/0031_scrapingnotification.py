import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0030_align_category_choices_with_constants"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScrapingNotification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("run_complete", "Run Complete"),
                            ("run_failed", "Run Failed"),
                            ("source_failing", "Source Failing"),
                            ("info", "Info"),
                        ],
                        max_length=32,
                    ),
                ),
                ("category", models.CharField(blank=True, default="", max_length=50)),
                ("message", models.CharField(max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="notifications",
                        to="scraping.scrapingrun",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="notifications",
                        to="scraping.scrapingsource",
                    ),
                ),
            ],
            options={
                "verbose_name": "Scraping Notification",
                "verbose_name_plural": "Scraping Notifications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="scrapingnotification",
            index=models.Index(
                fields=["is_read", "created_at"],
                name="idx_scrapenotif_read_created",
            ),
        ),
        migrations.AddIndex(
            model_name="scrapingnotification",
            index=models.Index(
                fields=["notification_type", "created_at"],
                name="idx_scrapenotif_type_created",
            ),
        ),
    ]
