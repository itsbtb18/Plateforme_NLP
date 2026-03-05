from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraping", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingrun",
            name="task_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Celery async task ID for status polling.",
                max_length=255,
                verbose_name="Celery Task ID",
            ),
        ),
    ]
