from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


class ChatSession(models.Model):
    """Store chat sessions for tracking and history"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', verbose_name=_("User"))
    fastapi_session_id = models.CharField(max_length=255, unique=True, verbose_name=_("FastAPI Session ID"))
    title = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    is_pinned = models.BooleanField(default=False, verbose_name=_("Is Pinned"))
    has_documents = models.BooleanField(default=False, verbose_name=_("Has Documents"))
    document_filename = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Document Filename"))
    
    # Content context - what the chat is about
    content_type = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Content Type"))
    object_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Object ID"))
    content_title = models.CharField(max_length=500, blank=True, null=True, verbose_name=_("Content Title"))
    
    class Meta:
        verbose_name = _("Chat Session")
        verbose_name_plural = _("Chat Sessions")
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['fastapi_session_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.fastapi_session_id[:8]}... ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class ChatMessage(models.Model):
    """Store individual chat messages"""
    MESSAGE_TYPES = (
        ('user', _('User')),
        ('bot', _('Bot')),
        ('system', _('System')),
        ('error', _('Error')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', verbose_name=_("Session"))
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, verbose_name=_("Message Type"))
    content = models.TextField(verbose_name=_("Content"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    source = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Source"))
    language = models.CharField(max_length=10, default='en', verbose_name=_("Language"))
    
    class Meta:
        verbose_name = _("Chat Message")
        verbose_name_plural = _("Chat Messages")
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}..."


class ChatFeedback(models.Model):
    """Store user feedback on bot responses"""
    RATING_CHOICES = (
        (1, _('Very Poor')),
        (2, _('Poor')),
        (3, _('Average')),
        (4, _('Good')),
        (5, _('Excellent')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='feedback', verbose_name=_("Message"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("User"))
    rating = models.IntegerField(choices=RATING_CHOICES, verbose_name=_("Rating"))
    comment = models.TextField(blank=True, null=True, verbose_name=_("Comment"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    
    class Meta:
        verbose_name = _("Chat Feedback")
        verbose_name_plural = _("Chat Feedback")
        ordering = ['-created_at']
        unique_together = ['message', 'user']
    
    def __str__(self):
        return f"{self.user.email} - Rating: {self.rating}/5"
