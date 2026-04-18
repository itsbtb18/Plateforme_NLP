from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraping", "0041_discoveredurl_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="mutation_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="last_mutated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discoveredurl",
            name="source_reason",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=80,
                verbose_name="Source Reason",
            ),
        ),
    ]
