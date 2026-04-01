from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0004_merge_20260227_0000"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="is_pinned",
            field=models.BooleanField(default=False, verbose_name="Is Pinned"),
        ),
    ]
