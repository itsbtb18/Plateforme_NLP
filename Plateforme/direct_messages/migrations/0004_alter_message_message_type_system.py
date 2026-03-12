from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("direct_messages", "0003_conversationparticipant_mute_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[("text", "Text"), ("link", "Link"), ("file", "File"), ("system", "System")],
                default="text",
                max_length=10,
            ),
        ),
    ]
