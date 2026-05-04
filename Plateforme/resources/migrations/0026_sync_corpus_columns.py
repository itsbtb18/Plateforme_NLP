from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0025_document_last_scraped_at_document_update_counter_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE resources_corpus
                    ADD COLUMN IF NOT EXISTS size integer;

                    UPDATE resources_corpus
                    SET size = 0
                    WHERE size IS NULL;

                    ALTER TABLE resources_corpus
                    ALTER COLUMN size SET NOT NULL;

                    ALTER TABLE resources_corpus
                    ADD COLUMN IF NOT EXISTS file_format varchar(10);

                    UPDATE resources_corpus
                    SET file_format = 'TXT'
                    WHERE file_format IS NULL OR file_format = '';

                    ALTER TABLE resources_corpus
                    ALTER COLUMN file_format SET NOT NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="corpus",
                    name="size",
                    field=models.IntegerField(
                        help_text="Size in number of words or documents",
                        verbose_name="Corpus Size",
                    ),
                ),
                migrations.AddField(
                    model_name="corpus",
                    name="file_format",
                    field=models.CharField(
                        max_length=10,
                        help_text="Format of the corpus (e.g., TXT, CSV, JSON)",
                        verbose_name="Format",
                    ),
                ),
            ],
        ),
    ]
