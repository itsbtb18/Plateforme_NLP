from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0018_scrapingsource_last_failed_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scrapingsource",
            name="last_error",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="consecutive_failures",
            field=models.IntegerField(default=0),
        ),
    ]
