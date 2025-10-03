from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    NOTIFICATION_TYPES = [
        ('SYSTEM', 'Système'),
        ('PROJECT_INVITATION', 'Invitation à un projet'),
        ('MEMBERSHIP_REQUEST', 'Demande d\'adhésion'),
        ('PROJECT_UPDATE', 'Mise à jour de projet'),
        ('TASK_ASSIGNED', 'Tâche assignée'),
        ('COMMENT', 'Commentaire'),
        ('EVENT_CREATED', 'Événement créé'),
        ('EVENT_APPROVED', 'Événement approuvé'),
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