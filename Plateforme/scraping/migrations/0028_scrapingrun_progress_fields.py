from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0027_align_canonical_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingrun",
            name="current_source",
            field=models.CharField(blank=True, max_length=255, verbose_name="Current Source"),
        ),
        migrations.AddField(
            model_name="scrapingrun",
            name="current_step",
            field=models.CharField(blank=True, max_length=100, verbose_name="Current Step"),
        ),
        migrations.AddField(
            model_name="scrapingrun",
            name="progress_current",
            field=models.IntegerField(default=0, verbose_name="Progress Current"),
        ),
        migrations.AddField(
            model_name="scrapingrun",
            name="progress_total",
            field=models.IntegerField(default=0, verbose_name="Progress Total"),
        ),
        migrations.AlterField(
            model_name="scrapingrun",
            name="items_created",
            field=models.IntegerField(default=0, verbose_name="Items Created"),
        ),
        migrations.AlterField(
            model_name="scrapingrun",
            name="items_skipped",
            field=models.IntegerField(default=0, verbose_name="Items Skipped"),
        ),
    ]
