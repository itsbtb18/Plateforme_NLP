# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_event_banner_image_event_is_hybrid_event_is_online_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='website',
            field=models.URLField(blank=True, db_index=True, verbose_name='Website'),
        ),
    ]
