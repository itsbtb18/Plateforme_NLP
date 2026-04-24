from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0007_alter_event_attachment_upload_to"),
    ]

    operations = [
        migrations.CreateModel(
            name="Speaker",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("affiliation", models.CharField(blank=True, max_length=255)),
                ("bio", models.TextField(blank=True)),
                ("talk_title", models.CharField(blank=True, max_length=255)),
                ("talk_abstract", models.TextField(blank=True)),
                ("website", models.URLField(blank=True)),
                (
                    "avatar",
                    models.ImageField(blank=True, null=True, upload_to="events/speakers/"),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="speakers",
                        to="events.event",
                    ),
                ),
            ],
            options={
                "verbose_name": "Speaker",
                "verbose_name_plural": "Speakers",
                "ordering": ["order", "name"],
            },
        ),
    ]
