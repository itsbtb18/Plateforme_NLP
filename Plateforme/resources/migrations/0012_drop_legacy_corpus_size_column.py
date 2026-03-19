# Generated manually to align legacy databases with the current Corpus model.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0011_alter_corpus_options_remove_document_file_format_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE resources_corpus DROP COLUMN IF EXISTS size;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
