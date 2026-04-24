# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('QA', '0004_add_post_bilingual_approval'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='source_url',
            field=models.URLField(blank=True, default='', db_index=True),
        ),
    ]
