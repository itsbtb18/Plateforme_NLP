from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0006_topic_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="replies",
                to="forum.message",
            ),
        ),
    ]
