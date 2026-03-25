# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('QA', '0003_post_news_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='source_url',
            field=models.URLField(blank=True, default='', db_index=True),
        ),
    ]
