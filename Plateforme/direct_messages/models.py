import mimetypes
import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _


ALLOWED_FILE_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mov", "docx", "mp3", "wav", "ogg", "m4a"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "audio/webm",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp4",
    "audio/x-m4a",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_CHAT_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


def _pair_order(user_a, user_b):
    if not user_a or not user_b:
        raise ValidationError(_("Both users are required."))
    if user_a == user_b:
        raise ValidationError(_("You cannot create a conversation with yourself."))
    return (user_a, user_b) if str(user_a.pk) < str(user_b.pk) else (user_b, user_a)


def validate_chat_file(uploaded_file):
    if not uploaded_file:
        return

    if uploaded_file.size > MAX_CHAT_FILE_SIZE:
        raise ValidationError(_("File size must be 5MB or less."))

    name = uploaded_file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValidationError(_("Unsupported file extension. Allowed: PDF, JPG, PNG, GIF, WEBP, MP4, WEBM, MOV, MP3, WAV, OGG, M4A, DOCX."))

    content_type = getattr(uploaded_file, "content_type", None)
    guessed_type, _ = mimetypes.guess_type(name)

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(_("Unsupported MIME type."))
    if guessed_type and guessed_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(_("File MIME type does not match allowed types."))


class Conversation(models.Model):
    class ConversationType(models.TextChoices):
        PRIVATE = "private", _("Private")
        GROUP = "group", _("Group")

    class ConversationStatus(models.TextChoices):
        PRIMARY = "primary", _("Primary")
        REQUEST = "request", _("Request")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_conversations_as_user1",
        null=True,
        blank=True,
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dm_conversations_as_user2",
        null=True,
        blank=True,
    )
    conversation_type = models.CharField(
        max_length=10,
        choices=ConversationType.choices,
        default=ConversationType.PRIVATE,
    )
    status = models.CharField(
        max_length=10,
        choices=ConversationStatus.choices,
        default=ConversationStatus.PRIMARY,
    )
    is_accepted = models.BooleanField(default=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dm_requested_conversations",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dm_created_conversations",
        null=True,
        blank=True,
    )
    group_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="dm_group_admin_conversations",
        null=True,
        blank=True,
    )
    group_name = models.CharField(max_length=120, blank=True, null=True)
    group_image = models.ImageField(upload_to="chat_groups/%Y/%m/%d/", blank=True, null=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConversationParticipant",
        related_name="dm_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"],
                condition=models.Q(conversation_type="private"),
                name="uniq_dm_private_conversation_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["user1", "created_at"]),
            models.Index(fields=["user2", "created_at"]),
            models.Index(fields=["conversation_type", "status", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.conversation_type == self.ConversationType.PRIVATE:
            if not self.user1_id or not self.user2_id:
                raise ValidationError(_("Private conversations require two users."))
            if self.user1_id == self.user2_id:
                raise ValidationError(_("Conversation participants must be different users."))
        elif not self.group_name:
            raise ValidationError(_("Group conversations require a group name."))

    @classmethod
    def get_or_create_for_users(cls, user_a, user_b):
        first, second = _pair_order(user_a, user_b)
        conversation, created = cls.objects.get_or_create(
            user1=first,
            user2=second,
            defaults={
                "conversation_type": cls.ConversationType.PRIVATE,
                "status": cls.ConversationStatus.PRIMARY,
                "is_accepted": True,
                "created_by": user_a,
            },
        )
        if created:
            conversation.participants.add(first, second)
        return conversation

    def has_participant(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.conversation_type == self.ConversationType.GROUP:
            return self.participants.filter(pk=user.pk).exists()
        return self.participants.filter(pk=user.pk).exists() or (self.user1_id == user.id or self.user2_id == user.id)

    def other_participant(self, user):
        if self.conversation_type != self.ConversationType.PRIVATE:
            return None
        if self.user1_id == user.id:
            return self.user2
        if self.user2_id == user.id:
            return self.user1
        return None

    @property
    def is_group(self):
        return self.conversation_type == self.ConversationType.GROUP

    def can_user_send(self, user):
        if not self.has_participant(user):
            return False
        if self.conversation_type == self.ConversationType.GROUP:
            return True
        if self.status == self.ConversationStatus.REQUEST and not self.is_accepted:
            return self.requested_by_id == user.id
        return True

    def is_request_for(self, user):
        if self.conversation_type != self.ConversationType.PRIVATE:
            return False
        if self.status != self.ConversationStatus.REQUEST or self.is_accepted:
            return False
        return self.has_participant(user) and self.requested_by_id != user.id

    def accept_request(self, user):
        if not self.is_request_for(user):
            raise ValidationError(_("Only the recipient can accept this request."))
        self.status = self.ConversationStatus.PRIMARY
        self.is_accepted = True
        self.save(update_fields=["status", "is_accepted"])

    def __str__(self):
        if self.is_group:
            return f"Group:{self.group_name} ({self.id})"
        return f"{self.user1_id} <-> {self.user2_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.conversation_type == self.ConversationType.PRIVATE and self.user1_id and self.user2_id:
            for uid in (self.user1_id, self.user2_id):
                ConversationParticipant.objects.get_or_create(
                    conversation=self,
                    user_id=uid,
                    defaults={"is_admin": uid == self.created_by_id},
                )


class ConversationParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participant_links")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dm_participations")
    is_admin = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)
    is_muted_indefinitely = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="uniq_dm_participant"),
        ]
        indexes = [
            models.Index(fields=["conversation", "joined_at"]),
            models.Index(fields=["user", "joined_at"]),
        ]

    def clean(self):
        super().clean()
        if self.conversation.conversation_type == Conversation.ConversationType.PRIVATE:
            if self.user_id not in (self.conversation.user1_id, self.conversation.user2_id):
                raise ValidationError(_("Private conversation participants must match user1/user2."))

    def __str__(self):
        return f"{self.conversation_id}:{self.user_id}"


class Message(models.Model):
    class MessageType(models.TextChoices):
        TEXT = "text", _("Text")
        LINK = "link", _("Link")
        FILE = "file", _("File")
        SYSTEM = "system", _("System")

    class SystemEventType(models.TextChoices):
        GROUP_CREATED = "group_created", _("Group created")
        MEMBER_ADDED = "member_added", _("Member added")
        MEMBER_REMOVED = "member_removed", _("Member removed")
        MEMBER_LEFT = "member_left", _("Member left")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dm_messages")
    message_type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField(blank=True, default="")
    file_path = models.FileField(upload_to="chat_files/%Y/%m/%d/", blank=True, null=True)
    system_event = models.CharField(max_length=32, choices=SystemEventType.choices, blank=True, default="")
    system_actor = models.CharField(max_length=255, blank=True, default="")
    system_target = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["conversation", "is_read"]),
        ]

    def clean(self):
        super().clean()
        if not self.conversation_id:
            # Conversation is assigned by the view before save; skip relation checks otherwise.
            return
        if not self.conversation.has_participant(self.sender):
            raise ValidationError(_("Sender must be a participant in the conversation."))

        safe_content = strip_tags(self.content or "").strip()
        if self.message_type == self.MessageType.FILE:
            if not self.file_path:
                raise ValidationError(_("A file is required for file messages."))
            validate_chat_file(self.file_path)
            self.content = safe_content
            return

        if self.message_type == self.MessageType.SYSTEM:
            if not self.system_event:
                raise ValidationError(_("System messages require an event type."))
            # Content is optional for system rows; keep sanitized text if provided.
            self.content = safe_content
            return

        if not safe_content:
            raise ValidationError(_("Message content cannot be empty."))

        if self.message_type == self.MessageType.LINK and not URL_RE.search(safe_content):
            raise ValidationError(_("Invalid link message content."))

        self.content = safe_content

    def save(self, *args, **kwargs):
        # Strip HTML tags to reduce stored XSS payload vectors.
        self.content = strip_tags(self.content or "").strip()

        if self.message_type == self.MessageType.TEXT and self.content and URL_RE.search(self.content):
            self.message_type = self.MessageType.LINK

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def extracted_links(self):
        return URL_RE.findall(self.content or "")
