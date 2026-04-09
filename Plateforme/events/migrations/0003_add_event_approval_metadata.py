# Generated to align DB schema with current Event model fields.

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models


def add_missing_event_fields(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    table_name = Event._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    fields_to_add = {
        "approval_date": models.DateTimeField(
            blank=True, null=True, verbose_name="Approval Date"
        ),
        # Add the raw FK column during the database step. Using a swappable
        # ForeignKey object inside RunPython can fail against the historical
        # app registry even though the final state operation is correct.
        "approved_by_id": models.UUIDField(
            blank=True,
            null=True,
            verbose_name="Approved By",
        ),
        "rejection_reason": models.TextField(
            blank=True, default="", verbose_name="Rejection Reason"
        ),
        "view_count": models.IntegerField(
            default=0,
            validators=[MinValueValidator(0)],
            verbose_name="View Count",
        ),
    }

    for field_name, field in fields_to_add.items():
        field.set_attributes_from_name(field_name)
        if field.column in existing_columns:
            continue
        schema_editor.add_field(Event, field)


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_pendingevent_event_approval_status_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_event_fields, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="event",
                    name="approval_date",
                    field=models.DateTimeField(blank=True, null=True, verbose_name="Approval Date"),
                ),
                migrations.AddField(
                    model_name="event",
                    name="approved_by",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="approved_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Approved By",
                    ),
                ),
                migrations.AddField(
                    model_name="event",
                    name="rejection_reason",
                    field=models.TextField(blank=True, default="", verbose_name="Rejection Reason"),
                ),
                migrations.AddField(
                    model_name="event",
                    name="view_count",
                    field=models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="View Count"),
                ),
            ],
        ),
    ]
