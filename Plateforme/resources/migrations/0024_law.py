from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("resources", "0023_resource_scrape_update_tracking"),
    ]

    operations = [
        migrations.CreateModel(
            name="Law",
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
                    "law_title",
                    models.CharField(blank=True, db_index=True, default="", max_length=300),
                ),
                ("authority", models.CharField(blank=True, default="", max_length=255)),
                (
                    "publication_date",
                    models.DateField(blank=True, db_index=True, null=True),
                ),
                ("legal_text", models.TextField(blank=True, default="")),
                ("category_tags", models.JSONField(blank=True, default=list)),
                ("source_url", models.URLField(blank=True, db_index=True, default="")),
                ("source_name", models.CharField(blank=True, default="", max_length=120)),
                (
                    "confidence_score",
                    models.FloatField(blank=True, db_index=True, null=True),
                ),
                (
                    "scrape_status",
                    models.CharField(
                        choices=[
                            ("PENDING_REVIEW", "Pending review"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                        ],
                        db_index=True,
                        default="PENDING_REVIEW",
                        max_length=20,
                    ),
                ),
                (
                    "approval_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("validation_notes", models.TextField(blank=True, default="")),
                ("is_approved", models.BooleanField(db_index=True, default=False)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="laws_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "last_scraped_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("update_counter", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "law",
                "verbose_name_plural": "Laws",
                "ordering": ["-publication_date", "-last_scraped_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="law",
            index=models.Index(fields=["law_title"], name="idx_law_title"),
        ),
        migrations.AddIndex(
            model_name="law",
            index=models.Index(fields=["source_url"], name="idx_law_source_url"),
        ),
        migrations.AddIndex(
            model_name="law",
            index=models.Index(fields=["publication_date"], name="idx_law_publication_date"),
        ),
    ]