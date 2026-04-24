from django.db import migrations


class Migration(migrations.Migration):
    """Compatibility migration to restore a missing graph node used by 0014 merge."""

    dependencies = [
        ("resources", "0010_drop_legacy_corpus_size_column"),
    ]

    operations = []
