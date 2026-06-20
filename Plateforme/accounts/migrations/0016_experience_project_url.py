from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_experience"),
    ]

    operations = [
        migrations.AddField(
            model_name="experience",
            name="project_url",
            field=models.URLField(blank=True),
        ),
    ]
