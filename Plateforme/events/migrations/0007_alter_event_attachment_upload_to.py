from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0006_domain_model_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="attachment",
            field=models.FileField(
                blank=True,
                help_text="Supported formats: PDF, DOC/DOCX, PPT/PPTX (Max 5MB)",
                null=True,
                upload_to="event_attachments/",
                verbose_name="Attachment",
            ),
        ),
    ]
