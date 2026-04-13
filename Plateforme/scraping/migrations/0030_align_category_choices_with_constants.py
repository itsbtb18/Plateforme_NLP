from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0029_scrapeditemmeta_translation_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scrapingsource",
            name="category",
            field=models.CharField(
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
        migrations.AlterField(
            model_name="searchquery",
            name="category",
            field=models.CharField(
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
    ]
