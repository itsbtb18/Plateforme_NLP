from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def backfill_participants_and_status(apps, schema_editor):
    Conversation = apps.get_model("direct_messages", "Conversation")
    ConversationParticipant = apps.get_model("direct_messages", "ConversationParticipant")

    for conv in Conversation.objects.all().iterator():
        if conv.user1_id and conv.user2_id:
            ConversationParticipant.objects.get_or_create(
                conversation_id=conv.id,
                user_id=conv.user1_id,
                defaults={"is_admin": False},
            )
            ConversationParticipant.objects.get_or_create(
                conversation_id=conv.id,
                user_id=conv.user2_id,
                defaults={"is_admin": False},
            )
            if not conv.created_by_id:
                conv.created_by_id = conv.user1_id
            if conv.is_accepted is None:
                conv.is_accepted = True
            if not conv.status:
                conv.status = "primary"
            if not conv.conversation_type:
                conv.conversation_type = "private"
            conv.save(
                update_fields=["created_by", "is_accepted", "status", "conversation_type"]
            )


class Migration(migrations.Migration):
    dependencies = [
        ("direct_messages", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="conversation",
            name="uniq_dm_conversation_pair",
        ),
        migrations.AlterField(
            model_name="conversation",
            name="user1",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dm_conversations_as_user1",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="user2",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="dm_conversations_as_user2",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="conversation_type",
            field=models.CharField(
                choices=[("private", "Private"), ("group", "Group")],
                default="private",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dm_created_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="group_admin",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dm_group_admin_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="group_image",
            field=models.ImageField(blank=True, null=True, upload_to="chat_groups/%Y/%m/%d/"),
        ),
        migrations.AddField(
            model_name="conversation",
            name="group_name",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="is_accepted",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dm_requested_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="status",
            field=models.CharField(
                choices=[("primary", "Primary"), ("request", "Request")],
                default="primary",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="ConversationParticipant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_admin", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participant_links",
                        to="direct_messages.conversation",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_participations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="conversation",
            name="participants",
            field=models.ManyToManyField(
                related_name="dm_conversations",
                through="direct_messages.ConversationParticipant",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["conversation_type", "status", "created_at"],
                name="direct_mess_convers_a4e816_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(conversation_type="private"),
                fields=("user1", "user2"),
                name="uniq_dm_private_conversation_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversationparticipant",
            constraint=models.UniqueConstraint(
                fields=("conversation", "user"),
                name="uniq_dm_participant",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationparticipant",
            index=models.Index(
                fields=["conversation", "joined_at"],
                name="direct_mess_convers_75c0dc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationparticipant",
            index=models.Index(
                fields=["user", "joined_at"],
                name="direct_mess_user_id_b5a5af_idx",
            ),
        ),
        migrations.RunPython(backfill_participants_and_status, migrations.RunPython.noop),
    ]
