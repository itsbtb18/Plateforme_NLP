from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0026_sync_corpus_columns"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE resources_document
                    ADD COLUMN IF NOT EXISTS file_format varchar(10);

                    UPDATE resources_document
                    SET file_format = 'PDF'
                    WHERE file_format IS NULL OR file_format = '';

                    ALTER TABLE resources_document
                    ALTER COLUMN file_format SET NOT NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="document",
                    name="file_format",
                    field=models.CharField(
                        max_length=10,
                        help_text="PDF, DOCX, TXT, etc.",
                        verbose_name="Format",
                    ),
                ),
            ],
        ),
    ]
