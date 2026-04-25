# Generated manually to merge divergent resources migration branches.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0025_add_document_scrape_fields"),
        ("resources", "0026_alter_corpus_deleted_by_alter_course_deleted_by_and_more"),
    ]

    operations = []
