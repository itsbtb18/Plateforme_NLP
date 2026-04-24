from django.db import migrations, models


def add_items_updated_if_missing(apps, schema_editor):
    ScrapingRun = apps.get_model("scraping", "ScrapingRun")
    table_name = ScrapingRun._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    if "items_updated" in existing_columns:
        return

    field = models.PositiveIntegerField(default=0, verbose_name="Items Updated")
    field.set_attributes_from_name("items_updated")
    schema_editor.add_field(ScrapingRun, field)


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0025_searchquery_model"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_items_updated_if_missing, migrations.RunPython.noop
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="scrapingrun",
                    name="items_updated",
                    field=models.PositiveIntegerField(
                        default=0, verbose_name="Items Updated"
                    ),
                ),
            ],
        ),
    ]
