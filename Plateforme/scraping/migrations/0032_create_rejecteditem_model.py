from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0031_scrapingnotification"),
    ]

    operations = [
        migrations.CreateModel(
            name="RejectedItem",
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
                        choices=[
                            ("events", "Events"),
                            ("tools", "Tools"),
                            ("courses", "Courses"),
                            ("news", "News"),
                            ("opportunities", "Opportunities"),
                            ("corpus", "Corpus"),
                        ],
                        max_length=50,
                        verbose_name="Category",
                    ),
                ),
                ("title", models.CharField(max_length=300, verbose_name="Title")),
                (
                    "reason_for_rejection",
                    models.TextField(verbose_name="Reason For Rejection"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
            ],
            options={
                "verbose_name": "Rejected Item",
                "verbose_name_plural": "Rejected Items",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["category", "created_at"],
                        name="idx_rejecteditem_cat_created",
                    )
                ],
            },
        ),
    ]
