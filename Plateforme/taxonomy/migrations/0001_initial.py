from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Dataset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("huggingface_id", models.CharField(blank=True, max_length=255, null=True)),
                ("paperswithcode_id", models.CharField(blank=True, max_length=255, null=True)),
                ("language", models.CharField(default="ar", max_length=20)),
                ("description_en", models.TextField(blank=True, default="")),
                ("description_ar", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Dataset",
                "verbose_name_plural": "Datasets",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="NLPMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_en", models.CharField(max_length=150)),
                ("name_ar", models.CharField(max_length=150)),
                ("slug", models.SlugField(unique=True)),
            ],
            options={
                "verbose_name": "NLP Method",
                "verbose_name_plural": "NLP Methods",
                "ordering": ["name_en"],
            },
        ),
        migrations.CreateModel(
            name="ResearchDomain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_en", models.CharField(max_length=150)),
                ("name_ar", models.CharField(max_length=150)),
                ("slug", models.SlugField(unique=True)),
                ("description_en", models.TextField(blank=True, default="")),
                ("description_ar", models.TextField(blank=True, default="")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="taxonomy.researchdomain",
                    ),
                ),
            ],
            options={
                "verbose_name": "Research Domain",
                "verbose_name_plural": "Research Domains",
                "ordering": ["name_en"],
            },
        ),
    ]

