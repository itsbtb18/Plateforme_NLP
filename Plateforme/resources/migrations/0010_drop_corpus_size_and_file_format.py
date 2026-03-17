from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("resources", "0009_corpus_rejection_reason_course_rejection_reason_and_more"),
    ]

    # Fields were already removed in earlier migration history on this branch.
    # Keep this migration as a no-op to preserve numbering and avoid state errors.
    operations = []
