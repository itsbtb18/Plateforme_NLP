# Generated manually to reconcile divergent events migration branches.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0007_event_entities"),
        ("events", "0007_alter_event_attachment_upload_to"),
        ("events", "0009_event_soft_delete_fields"),
    ]

    operations = []
