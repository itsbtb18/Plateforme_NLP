from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_project_rejection_reason_compat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectChatRoom",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chatroom",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project Chatroom",
                "verbose_name_plural": "Project Chatrooms",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="ProjectChatMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "message_type",
                    models.CharField(
                        choices=[("text", "Text"), ("link", "Link"), ("file", "File")],
                        default="text",
                        max_length=10,
                    ),
                ),
                ("content", models.TextField(blank=True, default="")),
                ("file_path", models.FileField(blank=True, null=True, upload_to="project_chat_files/%Y/%m/%d/")),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="projects.projectchatroom",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_chat_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "seen_by",
                    models.ManyToManyField(blank=True, related_name="seen_project_chat_messages", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Project Chat Message",
                "verbose_name_plural": "Project Chat Messages",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="projectchatmessage",
            index=models.Index(fields=["room", "created_at"], name="projects_pr_room_id_619130_idx"),
        ),
        migrations.AddIndex(
            model_name="projectchatmessage",
            index=models.Index(fields=["sender", "created_at"], name="projects_pr_sender__6902fa_idx"),
        ),
        migrations.AddIndex(
            model_name="projectchatmessage",
            index=models.Index(fields=["room", "is_deleted"], name="projects_pr_room_id_54be6c_idx"),
        ),
    ]
