from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("direct_messages", "0004_alter_message_message_type_system"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="system_actor",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="message",
            name="system_event",
            field=models.CharField(
                blank=True,
                choices=[
                    ("group_created", "Group created"),
                    ("member_added", "Member added"),
                    ("member_removed", "Member removed"),
                    ("member_left", "Member left"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="system_target",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
