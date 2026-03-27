from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0019_alter_scrapingsource_last_error_add_consecutive_failures"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="css_selectors",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="selector_recommendations",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="selector_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
