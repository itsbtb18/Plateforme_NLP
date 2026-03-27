from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraping", "0014_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrapingsource",
            name="fallback_url",
            field=models.URLField(blank=True, default="", verbose_name="Fallback URL"),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="fail_count",
            field=models.IntegerField(default=0, verbose_name="Fail Count"),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="last_error",
            field=models.TextField(blank=True, default="", verbose_name="Last Error"),
        ),
        migrations.AddField(
            model_name="scrapingsource",
            name="last_error_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Last Error At"),
        ),
    ]
