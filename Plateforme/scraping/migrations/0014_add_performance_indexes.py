# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraping', '0013_scrapeditemmeta_provenance_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='scrapingrun',
            index=models.Index(fields=['category', '-started_at'], name='idx_scrapingrun_cat_started'),
        ),
        migrations.AddIndex(
            model_name='scrapingsourcehealth',
            index=models.Index(fields=['category', 'source_name'], name='idx_sourcehealth_cat_source'),
        ),
    ]
