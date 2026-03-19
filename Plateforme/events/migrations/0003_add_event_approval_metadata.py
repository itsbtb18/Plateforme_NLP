# Generated to align DB schema with current Event model fields.

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_pendingevent_event_approval_status_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
    ]
