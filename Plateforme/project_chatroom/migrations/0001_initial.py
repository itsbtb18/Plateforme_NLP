# Generated migration for project_chatroom

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0004_pendingproject_project_approval_status_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectChat',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='chatroom', to='projects.project')),
            ],
            options={
                'verbose_name': 'Project Chat',
                'verbose_name_plural': 'Project Chats',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProjectChatMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_edited', models.BooleanField(default=False)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_chat_messages', to=settings.AUTH_USER_MODEL)),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='project_chatroom.projectchat')),
            ],
            options={
                'verbose_name': 'Project Chat Message',
                'verbose_name_plural': 'Project Chat Messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProjectChatFileAttachment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to='project_chat_attachments/%Y/%m/%d/')),
                ('attachment_type', models.CharField(choices=[('image', 'Image'), ('file', 'File')], default='file', max_length=20)),
                ('original_filename', models.CharField(max_length=255)),
                ('file_size', models.BigIntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='project_chatroom.projectchatmessage')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_chat_attachments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Project Chat File Attachment',
                'verbose_name_plural': 'Project Chat File Attachments',
                'ordering': ['uploaded_at'],
            },
        ),
    ]
