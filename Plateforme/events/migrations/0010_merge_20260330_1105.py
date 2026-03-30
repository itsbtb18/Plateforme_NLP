# Generated manually to reconcile divergent events migration branches.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0007_event_entities"),
        ("events", "0007_merge_20260325_1814"),
        ("events", "0007_merge_20260326_2135"),
        ("events", "0009_event_soft_delete_fields"),
    ]

    operations = []
