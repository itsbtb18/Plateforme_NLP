from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
import uuid

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    NOTIFICATION_TYPES = [
        # System & General
        ('SYSTEM', _('System')),
        
        # Project-related
        ('PROJECT_INVITATION', _('Project Invitation')),
        ('MEMBERSHIP_REQUEST', _('Membership Request')),
        ('PROJECT_UPDATE', _('Project Update')),
        ('TASK_ASSIGNED', _('Task Assigned')),
        ('LEAVE_REQUEST', _('Leave Request')),
        
        # Community & Communication
        ('COMMENT', _('Comment')),
        ('MESSAGE', _('Message')),
        
        # Events
        ('EVENT_CREATED', _('Event Created')),
        ('EVENT_APPROVED', _('Event Approved')),
        
        # Resources & Tools (Academic)
        ('RESOURCE_ADDED', _('New Resource')),
        ('TOOL_ADDED', _('New Tool')),
        ('CORPUS_UPDATE', _('Corpus Update')),
        ('RESEARCH_UPDATE', _('Research Update')),
        
        # Forum & Q&A (Community)
        ('FORUM_TOPIC', _('Forum Topic')),
        ('QA_ANSWER', _('Q&A Answer')),
        ('QA_COMMENT', _('Q&A Comment')),
        ('POST_APPROVED', _('Post Approved')),
        
        # Institution
        ('INSTITUTION_UPDATE', _('Institution Update')),
    ]
    response_given = models.BooleanField(default=False)
    response = models.CharField(
        max_length=10, 
        choices=[
            ('accept', 'Accept'),
            ('reject', 'Reject'),
        ],
        null=True, 
        blank=True
    )
    response_date = models.DateTimeField(null=True, blank=True)
    recipient = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='SYSTEM')
    title = models.CharField(max_length=255)
    title_en = models.CharField(_("Title (English)"), max_length=255, blank=True, default='')
    title_ar = models.CharField(_("Title (Arabic)"), max_length=255, blank=True, default='')
    message = models.TextField()
    message_en = models.TextField(_("Message (English)"), blank=True, default='')
    message_ar = models.TextField(_("Message (Arabic)"), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Champs pour lier à n'importe quel modèle (ContentType framework)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Champs spécifiques pour les actions liées aux projets
    project_id = models.UUIDField(null=True, blank=True)
    sender_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Auto-populate bilingual fields from title/message if not already set."""
        from django.utils.translation import override as translation_override
        # If bilingual fields are empty, try to resolve from the (possibly lazy) title/message
        if self.title and not self.title_en:
            try:
                with translation_override('en'):
                    self.title_en = str(self.title)
            except Exception:
                self.title_en = str(self.title)
        if self.title and not self.title_ar:
            try:
                with translation_override('ar'):
                    resolved = str(self.title)
                    self.title_ar = resolved
            except Exception:
                pass
        if self.message and not self.message_en:
            try:
                with translation_override('en'):
                    self.message_en = str(self.message)
            except Exception:
                self.message_en = str(self.message)
        if self.message and not self.message_ar:
            try:
                with translation_override('ar'):
                    resolved = str(self.message)
                    self.message_ar = resolved
            except Exception:
                pass
        # Ensure legacy title/message fields have the English version
        if self.title_en and not self.title:
            self.title = self.title_en
        if self.message_en and not self.message:
            self.message = self.message_en
        super().save(*args, **kwargs)

    def get_localized_title(self):
        """Return title based on current language with fallback."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar') and self.title_ar:
            return self.title_ar
        if self.title_en:
            return self.title_en
        return self.title

    def get_localized_message(self):
        """Return message based on current language with fallback."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar') and self.message_ar:
            return self.message_ar
        if self.message_en:
            return self.message_en
        return self.message

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
        
    def get_type_display(self):
        """Retourne l'affichage du type de notification"""
        for type_code, type_display in self.NOTIFICATION_TYPES:
            if self.type == type_code:
                return type_display
        return "Inconnu"