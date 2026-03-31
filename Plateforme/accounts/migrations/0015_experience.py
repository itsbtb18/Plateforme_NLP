from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_follow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Experience",
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
                    "experience_type",
                    models.CharField(
                        choices=[
                            ("professional", "Professional"),
                            ("project", "Project"),
                            ("event", "Event"),
                        ],
                        default="professional",
                        max_length=20,
                    ),
                ),
                ("institution_name", models.CharField(max_length=255)),
                ("role_title", models.CharField(max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("is_current", models.BooleanField(default=False)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="experiences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-start_date", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["user", "-start_date"],
                        name="accounts_ex_user_id_5d5f92_idx",
                    )
                ],
            },
        ),
    ]
