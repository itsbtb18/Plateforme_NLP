# Generated manually to align legacy databases with the current Corpus model.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("resources", "0010_drop_legacy_corpus_size_column")]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE resources_corpus DROP COLUMN IF EXISTS file_format;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
