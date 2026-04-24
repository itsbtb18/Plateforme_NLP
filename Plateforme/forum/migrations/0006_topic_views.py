from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0005_topic_rejection_reason_compat"),
    ]

    operations = [
        migrations.AddField(
            model_name="topic",
            name="views",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
