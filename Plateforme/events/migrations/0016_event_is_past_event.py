from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0015_event_update_counter"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="is_past_event",
            field=models.BooleanField(
                db_index=True,
                default=False,
                verbose_name="Is Past Event",
            ),
        ),
    ]
