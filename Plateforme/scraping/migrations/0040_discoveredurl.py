from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0039_remove_institutions_periodic_task"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscoveredURL",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        db_index=True,
                        default="events",
                        max_length=50,
                        verbose_name="Category",
                    ),
                ),
                ("url", models.URLField(unique=True, verbose_name="URL")),
                (
                    "source_page_url",
                    models.URLField(
                        blank=True,
                        default="",
                        verbose_name="Source Page URL",
                    ),
                ),
                (
                    "section_label",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Section Label",
                    ),
                ),
                (
                    "discovery_method",
                    models.CharField(
                        choices=[
                            ("css", "CSS Selector"),
                            ("llm", "LLM Scan"),
                            ("heuristic", "Heuristic"),
                        ],
                        default="heuristic",
                        max_length=20,
                        verbose_name="Discovery Method",
                    ),
                ),
                (
                    "keywords_hit",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="Keywords Hit",
                    ),
                ),
                (
                    "priority_score",
                    models.IntegerField(
                        db_index=True,
                        default=0,
                        verbose_name="Priority Score",
                    ),
                ),
                (
                    "times_seen",
                    models.PositiveIntegerField(default=1, verbose_name="Times Seen"),
                ),
                (
                    "is_processed",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        verbose_name="Is Processed",
                    ),
                ),
                (
                    "first_discovered_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="First Discovered At",
                    ),
                ),
                (
                    "last_discovered_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="Last Discovered At",
                    ),
                ),
            ],
            options={
                "db_table": "discovered_urls",
                "verbose_name": "Discovered URL",
                "verbose_name_plural": "Discovered URLs",
                "ordering": ["-priority_score", "-times_seen", "-last_discovered_at"],
                "indexes": [
                    models.Index(
                        fields=["category", "is_processed", "priority_score"],
                        name="idx_discoveredurl_queue",
                    ),
                ],
            },
        ),
    ]
