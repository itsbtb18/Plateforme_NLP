from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0017_scrapingsource_validation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="last_failed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Last Failed At"),
        ),
    ]
