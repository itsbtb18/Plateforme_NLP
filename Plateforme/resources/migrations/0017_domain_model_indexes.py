# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0016_alter_corpus_options_remove_document_file_format_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='corpus',
            name='access_link',
            field=models.URLField(blank=True, db_index=True, null=True, verbose_name='Access Link'),
        ),
        migrations.AlterField(
            model_name='course',
            name='access_link',
            field=models.URLField(blank=True, db_index=True, null=True, verbose_name='Access Link'),
        ),
        migrations.AlterField(
            model_name='document',
            name='access_link',
            field=models.URLField(blank=True, db_index=True, null=True, verbose_name='Access Link'),
        ),
        migrations.AlterField(
            model_name='nlptool',
            name='access_link',
            field=models.URLField(blank=True, db_index=True, null=True, verbose_name='Access Link'),
        ),
    ]
