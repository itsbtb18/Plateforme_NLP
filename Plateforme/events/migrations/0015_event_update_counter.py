from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0014_event_scrape_review_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="update_counter",
            field=models.PositiveIntegerField(default=0, verbose_name="Update Counter"),
        ),
    ]
