from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("institutions", "0013_domain_model_indexes"),
        ("pages", "0007_newspublication"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Opportunity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, default="", max_length=255)),
                ("title_en", models.CharField(max_length=255)),
                ("title_ar", models.CharField(max_length=255)),
                ("opportunity_type", models.CharField(choices=[("job", "Job"), ("internship", "Internship"), ("pfe", "PFE / Master"), ("phd", "PhD"), ("collab", "Collaboration")], max_length=20)),
                ("organization_en", models.CharField(blank=True, default="", max_length=255)),
                ("organization_ar", models.CharField(blank=True, default="", max_length=255)),
                ("location", models.CharField(max_length=255)),
                ("mode", models.CharField(choices=[("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")], max_length=20)),
                ("level", models.CharField(choices=[("student", "Student"), ("junior", "Junior"), ("senior", "Senior"), ("researcher", "Researcher")], max_length=20)),
                ("description", models.TextField(validators=[django.core.validators.MinLengthValidator(40)])),
                ("skills", models.JSONField(blank=True, default=list)),
                ("contact", models.CharField(max_length=255)),
                ("deadline", models.DateField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=20)),
                ("approval_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=20)),
                ("is_published", models.BooleanField(db_index=True, default=False)),
                ("user_role", models.CharField(default="user", max_length=32)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opportunities_moderated", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="opportunities_created", to=settings.AUTH_USER_MODEL)),
                ("institution", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opportunities", to="institutions.institution")),
            ],
            options={
                "verbose_name": "Opportunity",
                "verbose_name_plural": "Opportunities",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(fields=["status", "is_published"], name="pages_oppor_status_8dc9f4_idx"),
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(fields=["approval_status", "created_at"], name="pages_oppor_approva_3da984_idx"),
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(fields=["created_by", "status"], name="pages_oppor_created_3778d0_idx"),
        ),
        migrations.AddIndex(
            model_name="opportunity",
            index=models.Index(fields=["deadline"], name="pages_oppor_deadlin_04b584_idx"),
        ),
    ]
