from django.db import models
from django.urls import reverse
from django.conf import settings
from institutions.models import Institution
import uuid
import mimetypes
import re
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django.db.models import Manager, QuerySet
from typing import Any
from datetime import datetime, date
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

class User(models.Model):
    id: int
    full_name: str
    is_staff: bool
    is_superuser: bool
    is_active: bool

class ProjectMemberQuerySet(QuerySet["ProjectMember"]): ...

class ProjectMemberManager(Manager["ProjectMember"]):
    def filter(self, *args: Any, **kwargs: Any) -> ProjectMemberQuerySet: ...
    def get(self, *args: Any, **kwargs: Any) -> "ProjectMember": ...

class ProjectQuerySet(QuerySet["Project"]): ...

class ProjectManager(Manager["Project"]):
    def filter(self, *args: Any, **kwargs: Any) -> ProjectQuerySet: ...
    def get(self, *args: Any, **kwargs: Any) -> "Project": ...

class Project(models.Model):
    STATUS_CHOICES = (
        ('ongoing', pgettext_lazy('project_status', 'Ongoing')),
        ('completed', pgettext_lazy('project_status', 'Completed')),          
        ('planned', pgettext_lazy('project_status', 'Planned')),    
    )
    APPROVAL_STATUS_CHOICES = (
        ('pending', pgettext_lazy('approval_status', 'Pending')),
        ('approved', pgettext_lazy('approval_status', 'Approved')),
        ('rejected', pgettext_lazy('approval_status', 'Rejected')),
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=255)
    title_ar = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Title (Arabic)'))
    title_en = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Title (English)'))
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ongoing'
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name=_('Approval Status')
    )
    rejection_reason = models.TextField(
        verbose_name=_('Rejection Reason'),
        blank=True,
        null=True,
        default='',
        help_text=_('Reason for rejection (only filled when status is rejected)')
    )
    # Kept for DB compatibility: some deployments still have a NOT NULL is_approved column.
    is_approved = models.BooleanField(default=False, verbose_name=_('Is Approved'))
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coordinated_projects'
    )
    description = models.TextField()
    description_ar = models.TextField(blank=True, default='', verbose_name=_('Description (Arabic)'))
    description_en = models.TextField(blank=True, default='', verbose_name=_('Description (English)'))
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)
    attachment = models.FileField(upload_to='project_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_start', 'title']
        verbose_name = _('Project')
        verbose_name_plural = _('Projects')

    def __str__(self):
        return self.title

    def get_localized_title(self):
        """Return title based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.title_ar:
            return self.title_ar
        elif self.title_en:
            return self.title_en
        return self.title

    def get_localized_description(self):
        """Return description based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.description_ar:
            return self.description_ar
        elif self.description_en:
            return self.description_en
        return self.description

    @property
    def title_display(self):
        """Return title based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar'):
            return self.title_ar or ''
        return self.title_en or ''

    @property
    def description_display(self):
        """Return description based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar'):
            return self.description_ar or ''
        return self.description_en or ''

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})


class ProjectMember(models.Model):
    STATUS_CHOICES = (
        ('pending', pgettext_lazy('member_status', 'Pending')),
        ('accepted', pgettext_lazy('member_status', 'Accepted')),
        ('rejected', pgettext_lazy('member_status', 'Rejected')),
    )
    LEAVE_REQUEST_STATUS_CHOICES = [
        ('none', pgettext_lazy('leave_status', 'None')),
        ('pending', pgettext_lazy('leave_status', 'Pending')),
        ('rejected', pgettext_lazy('leave_status', 'Rejected')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    role = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    leave_request_status = models.CharField(
        max_length=10, 
        choices=LEAVE_REQUEST_STATUS_CHOICES, 
        default='none'
    )
    leave_request_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('project', 'member')
        ordering = ['project', 'member']
        verbose_name = _('Project Member')
        verbose_name_plural = _('Project Members')

    def __str__(self):
        return f"{self.member.full_name} - {self.project.title}"

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.project.pk})


class ProjectInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACCEPTED = 'accepted', _('Accepted')
        REJECTED = 'rejected', _('Rejected')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_invitations'
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_project_invitations'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['invited_user', 'status']),
        ]
        verbose_name = _('Project Invitation')
        verbose_name_plural = _('Project Invitations')

    def __str__(self):
        return f"{self.project_id} -> {self.invited_user_id} ({self.status})"


PROJECT_CHAT_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "zip"}
PROJECT_CHAT_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "application/x-zip-compressed",
    "multipart/x-zip",
}
PROJECT_CHAT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
PROJECT_CHAT_URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


def validate_project_chat_file(uploaded_file):
    if not uploaded_file:
        return

    if uploaded_file.size > PROJECT_CHAT_MAX_FILE_SIZE:
        raise ValidationError(_("File size must be 10MB or less."))

    name = uploaded_file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in PROJECT_CHAT_ALLOWED_EXTENSIONS:
        raise ValidationError(_("Unsupported file extension. Allowed: PDF, JPG, PNG, DOCX, ZIP."))

    content_type = getattr(uploaded_file, "content_type", None)
    guessed_type, _ = mimetypes.guess_type(name)
    if content_type and content_type not in PROJECT_CHAT_ALLOWED_MIME_TYPES:
        raise ValidationError(_("Unsupported MIME type."))
    if guessed_type and guessed_type not in PROJECT_CHAT_ALLOWED_MIME_TYPES:
        raise ValidationError(_("File MIME type does not match allowed types."))


class ProjectChatRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='chat_rooms')
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='chatroom_room')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = _('Project Chatroom')
        verbose_name_plural = _('Project Chatrooms')

    def __str__(self):
        return f"Chatroom - {self.project.title}"

    def user_is_member(self, user):
        if not user or not user.is_authenticated:
            return False
        if user == self.project.coordinator:
            return True
        return ProjectMember.objects.filter(project=self.project, member=user, status='accepted').exists()


class ProjectChatMessage(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', _('Text')
        LINK = 'link', _('Link')
        FILE = 'file', _('File')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ProjectChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_chat_sent_messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_project_chat_messages')
    message_type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField(blank=True, default='')
    file_path = models.FileField(upload_to='project_chat_files/%Y/%m/%d/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    seen_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='seen_project_chat_messages', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['room', 'is_deleted']),
        ]
        verbose_name = _('Project Chat Message')
        verbose_name_plural = _('Project Chat Messages')

    def clean(self):
        super().clean()
        if not self.room_id:
            return
        if not self.room.user_is_member(self.sender):
            raise ValidationError(_("Sender must be a project member."))

        safe_content = strip_tags(self.content or "").strip()
        if self.message_type == self.MessageType.FILE:
            if not self.file_path:
                raise ValidationError(_("A file is required for file messages."))
            validate_project_chat_file(self.file_path)
            self.content = safe_content
            return

        if not safe_content:
            raise ValidationError(_("Message content cannot be empty."))
        if self.message_type == self.MessageType.LINK and not PROJECT_CHAT_URL_RE.search(safe_content):
            raise ValidationError(_("Invalid link content."))
        self.content = safe_content

    def save(self, *args, **kwargs):
        self.content = strip_tags(self.content or "").strip()
        if self.message_type == self.MessageType.TEXT and self.content and PROJECT_CHAT_URL_RE.search(self.content):
            self.message_type = self.MessageType.LINK
        self.full_clean()
        super().save(*args, **kwargs)
