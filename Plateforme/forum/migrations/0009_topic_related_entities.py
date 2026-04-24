from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("QA", "0009_post_authors_post_news_category_post_published_date_and_more"),
        ("events", "0007_alter_event_attachment_upload_to"),
        ("forum", "0008_message_rendered_content"),
        ("projects", "0011_project_taxonomy_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="topic",
            name="related_event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="forum_topics",
                to="events.event",
            ),
        ),
        migrations.AddField(
            model_name="topic",
            name="related_news",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="forum_topics",
                to="QA.post",
            ),
        ),
        migrations.AddField(
            model_name="topic",
            name="related_project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="forum_topics",
                to="projects.project",
            ),
        ),
    ]
