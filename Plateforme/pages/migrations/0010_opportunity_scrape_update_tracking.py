from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0009_opportunity_scrape_review_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="opportunity",
            name="last_scraped_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="update_counter",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
