from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from projects.models import Project
import uuid


User = get_user_model()


class ProjectChat(models.Model):
    """
    Private chatroom for project members to discuss and collaborate.
    One chatroom per project, accessible only by project members.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='chatroom'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project Chat'
        verbose_name_plural = 'Project Chats'

    def __str__(self):
        return f"Chat for {self.project.title}"

    def get_absolute_url(self):
        return reverse('project_chatroom:chat-detail', kwargs={'pk': self.pk})

    def get_members(self):
        """Get all accepted members of the project"""
        from projects.models import ProjectMember
        return self.project.members.filter(status='accepted').select_related('member')

    def can_user_access(self, user):
        """Check if user is a member of the project"""
        if not user.is_authenticated:
            return False
        from projects.models import ProjectMember
        return ProjectMember.objects.filter(
            project=self.project,
            member=user,
            status='accepted'
        ).exists()


class ProjectChatMessage(models.Model):
    """
    Messages in project chatroom with support for file attachments.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    chat = models.ForeignKey(
        ProjectChat,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_chat_messages'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Project Chat Message'
        verbose_name_plural = 'Project Chat Messages'

    def __str__(self):
        return f"Message from {self.author.full_name} in {self.chat.project.title}"


class ProjectChatFileAttachment(models.Model):
    """
    File and photo attachments for project chat messages.
    """
    ATTACHMENT_TYPE_CHOICES = (
        ('image', _('Image')),
        ('file', _('File')),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    message = models.ForeignKey(
        ProjectChatMessage,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(
        upload_to='project_chat_attachments/%Y/%m/%d/'
    )
    attachment_type = models.CharField(
        max_length=20,
        choices=ATTACHMENT_TYPE_CHOICES,
        default='file'
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # in bytes
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='project_chat_attachments'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Project Chat File Attachment'
        verbose_name_plural = 'Project Chat File Attachments'

    def __str__(self):
        return f"{self.original_filename} in {self.message.chat.project.title}"

    def get_file_extension(self):
        """Get file extension"""
        import os
        return os.path.splitext(self.original_filename)[1].lower()

    def is_image(self):
        """Check if attachment is an image"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        return self.get_file_extension() in image_extensions
