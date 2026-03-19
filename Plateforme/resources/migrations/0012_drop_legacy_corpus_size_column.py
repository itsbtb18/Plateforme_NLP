# Generated manually to align legacy databases with the current Corpus model.

from django.db import migrations


class Migration(migrations.Migration):

    # Note: 0011 was removed; point to the latest existing migration (0009...)
    dependencies = [
        ("resources", "0009_corpus_rejection_reason_course_rejection_reason_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE resources_corpus DROP COLUMN IF EXISTS size;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
