# Generated manually to reconcile divergent resources migration branches.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0019_corpus_rejection_reason_course_rejection_reason_and_more"),
        ("resources", "0019_resource_entities"),
        ("resources", "0019_resource_soft_delete_fields"),
        ("resources", "0020_alter_corpus_options_remove_document_file_format_and_more"),
    ]

    operations = []
