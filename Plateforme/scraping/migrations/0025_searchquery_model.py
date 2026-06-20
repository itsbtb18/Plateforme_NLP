# Generated manually to add missing SearchQuery table

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraping", "0024_scrapingsource_force_playwright_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchQuery",
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
                            ("news", "News"),
                            ("tools", "Tools"),
                            ("courses", "Courses"),
                            ("opportunities", "Opportunities"),
                            ("corpus", "Corpus"),
                        ],
                        max_length=50,
                        verbose_name="Category",
                    ),
                ),
                (
                    "query_text",
                    models.CharField(max_length=500, verbose_name="Query Text"),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Active"),
                ),
            ],
            options={
                "verbose_name": "Search Query",
                "verbose_name_plural": "Search Queries",
                "ordering": ["category", "id"],
                "indexes": [
                    models.Index(
                        fields=["category", "is_active"],
                        name="idx_searchquery_cat_active",
                    )
                ],
            },
        ),
    ]
