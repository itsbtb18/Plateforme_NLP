from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("direct_messages", "0002_instagram_dm_upgrade"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationparticipant",
            name="is_muted_indefinitely",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="conversationparticipant",
            name="muted_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

