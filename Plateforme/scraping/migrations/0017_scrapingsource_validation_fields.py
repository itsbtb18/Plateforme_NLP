from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0016_scrapingsource_url_and_source_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="last_validated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="validation_detail",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="validation_status",
            field=models.CharField(
                choices=[
                    ("GREEN", "OK"),
                    ("YELLOW", "Avertissement"),
                    ("RED", "Probleme"),
                    ("PENDING", "En cours"),
                    ("UNKNOWN", "Non teste"),
                ],
                default="UNKNOWN",
                max_length=10,
            ),
        ),
    ]
