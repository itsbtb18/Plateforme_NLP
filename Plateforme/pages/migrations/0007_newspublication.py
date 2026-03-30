from django.conf import settings
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
import pages.models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0006_rename_pages_adminlog_user_time_idx_pages_admin_admin_u_e3a4a0_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsPublication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("type", models.CharField(choices=[("paper", "Paper"), ("dataset", "Dataset"), ("tool", "Tool"), ("event", "Event"), ("thesis", "Thesis"), ("news", "News")], default="news", max_length=20)),
                ("abstract", models.TextField(validators=[MinLengthValidator(150)])),
                ("authors", models.JSONField(blank=True, default=list)),
                ("affiliations", models.CharField(blank=True, default="", max_length=255)),
                ("year", models.IntegerField(default=timezone.now().year, validators=[MinValueValidator(1900), MaxValueValidator(2100)])),
                ("venue", models.CharField(blank=True, default="", max_length=255)),
                ("nlp_tasks", models.JSONField(blank=True, default=list)),
                ("languages", models.JSONField(blank=True, default=list)),
                ("keywords", models.JSONField(blank=True, default=list)),
                ("doi", models.CharField(blank=True, max_length=255, null=True)),
                ("pdf_url", models.URLField(blank=True, null=True)),
                ("github_url", models.URLField(blank=True, null=True)),
                ("dataset_url", models.URLField(blank=True, null=True)),
                ("demo_url", models.URLField(blank=True, null=True)),
                ("cover_image", models.ImageField(blank=True, null=True, upload_to=pages.models.news_cover_upload_to)),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to=pages.models.news_pdf_upload_to)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="published", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="news_publications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "News Publication",
                "verbose_name_plural": "News Publications",
                "ordering": ["-year", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="newspublication",
            index=models.Index(fields=["type", "status"], name="pages_newsp_type_4cbbc1_idx"),
        ),
        migrations.AddIndex(
            model_name="newspublication",
            index=models.Index(fields=["year", "status"], name="pages_newsp_year_654c4f_idx"),
        ),
        migrations.AddIndex(
            model_name="newspublication",
            index=models.Index(fields=["created_at"], name="pages_newsp_create_3d07e8_idx"),
        ),
    ]
