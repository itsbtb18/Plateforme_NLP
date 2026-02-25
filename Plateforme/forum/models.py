from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
import uuid


class Topic(models.Model):
    APPROVAL_STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    )
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Title (Arabic)'))
    title_en = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Title (English)'))
    description = models.TextField()
    description_ar = models.TextField(blank=True, default='', verbose_name=_('Description (Arabic)'))
    description_en = models.TextField(blank=True, default='', verbose_name=_('Description (English)'))
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='topics')
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name=_('Approval Status')
    )
    # Legacy field for backward compatibility
    is_approved = models.BooleanField(default=False, verbose_name=_('Is Approved'))

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
        return reverse('forum:topic-list')

class ChatRoom(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='chatrooms')
    name = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Name (Arabic)'))
    name_en = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Name (English)'))
    description = models.TextField()
    description_ar = models.TextField(blank=True, default='', verbose_name=_('Description (Arabic)'))
    description_en = models.TextField(blank=True, default='', verbose_name=_('Description (English)'))
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='created_chatrooms')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def get_localized_name(self):
        """Return name based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar') and self.name_ar:
            return self.name_ar
        elif self.name_en:
            return self.name_en
        return self.name

    def get_localized_description(self):
        """Return description based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar') and self.description_ar:
            return self.description_ar
        elif self.description_en:
            return self.description_en
        return self.description
    
    def get_absolute_url(self):
        return reverse('forum:chatroom-detail', kwargs={'pk': self.pk})

class Message(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='forum_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']  # Tri par défaut des messages par ordre chronologique

    def __str__(self):
        return f"Message de {self.user.email} à {self.timestamp.strftime('%H:%M:%S')}"

class BannedUser(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='banned_users')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='banned_from_chatrooms')
    banned_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, related_name='banned_users')
    banned_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['chatroom', 'user']
        ordering = ['-banned_at']

    def __str__(self):
        return f"{self.user.email} banni de {self.chatroom.name}"