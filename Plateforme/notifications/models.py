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
    message = models.TextField()
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

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
        
    def get_type_display(self):
        """Retourne l'affichage du type de notification"""
        for type_code, type_display in self.NOTIFICATION_TYPES:
            if self.type == type_code:
                return type_display
        return "Inconnu"