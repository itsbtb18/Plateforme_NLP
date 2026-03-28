from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("institutions", "0013_domain_model_indexes"),
        ("accounts", "0011_rename_accounts_fr_request_a3ba9b_idx_accounts_fr_request_ca3f99_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("taxonomy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bio", models.TextField(blank=True, default="")),
                (
                    "orcid",
                    models.CharField(
                        blank=True,
                        max_length=19,
                        null=True,
                        validators=[
                            RegexValidator(
                                message="ORCID must be in the format 0000-0000-0000-0000.",
                                regex="^\\d{4}-\\d{4}-\\d{4}-\\d{3}[\\dX]$",
                            )
                        ],
                    ),
                ),
                ("github_username", models.CharField(blank=True, max_length=39, null=True)),
                ("linkedin_url", models.URLField(blank=True, null=True)),
                ("website", models.URLField(blank=True, null=True)),
                ("is_independent", models.BooleanField(default=False)),
                ("country", models.CharField(blank=True, max_length=100, null=True)),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="profiles/avatars/%Y/%m/%d/")),
                ("show_online_status", models.BooleanField(default=True)),
                (
                    "institution",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_profiles",
                        to="institutions.institution",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "expertise_tags",
                    models.ManyToManyField(blank=True, related_name="user_profiles", to="taxonomy.researchdomain"),
                ),
            ],
            options={
                "verbose_name": "user profile",
                "verbose_name_plural": "user profiles",
            },
        ),
    ]
