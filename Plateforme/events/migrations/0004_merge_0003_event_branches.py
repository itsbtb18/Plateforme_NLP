from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0003_add_event_approval_metadata"),
        ("events", "0003_event_source"),
    ]

    operations = []
