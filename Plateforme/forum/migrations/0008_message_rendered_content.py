from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0007_message_parent"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="rendered_content",
            field=models.TextField(blank=True, default=""),
        ),
    ]
