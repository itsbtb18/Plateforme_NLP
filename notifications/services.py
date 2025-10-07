from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from django.contrib.contenttypes.models import ContentType
from .models import Notification

class NotificationService:
    @staticmethod
    def create_notification(recipient, notification_type, title, message, related_object=None, project_id=None, sender_id=None):
        """
        Crée une notification et l'envoie via WebSocket si possible
        
        Args:
            recipient: Utilisateur qui recevra la notification
            notification_type: Type de notification (utiliser NotificationType)
            title: Titre de la notification
            message: Message détaillé
            related_object: Objet associé à la notification (optionnel)
            project_id: ID du projet concerné (pour les invitations ou demandes)
            sender_id: ID de l'expéditeur (pour les invitations ou demandes)
        """
        # Créer l'objet notification
        notification = Notification(
            recipient=recipient,
            type=notification_type,
            title=title,
            message=message,
            project_id=project_id,
            sender_id=sender_id
        )
        
        # Ajouter l'objet associé si fourni
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            notification.content_type = content_type
            notification.object_id = related_object.id
        
        notification.save()
        
        # Envoyer la notification par WebSocket
        channel_layer = get_channel_layer()
        user_group_name = f"user_{recipient.id}_notifications"
        
        notification_data = {
            'id': notification.id,
            'type': notification.get_type_display(),
            'title': notification.title,
            'message': notification.message,
            'created_at': notification.created_at.isoformat(),
            'project_id': str(notification.project_id) if notification.project_id else None,
            'sender_id': str(notification.sender_id) if notification.sender_id else None
        }
        
        try:
            async_to_sync(channel_layer.group_send)(
                user_group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )
        except Exception as e:
            # Gérer le cas où le WebSocket n'est pas disponible
            # La notification est déjà sauvegardée en base de données
            print(f"Erreur WebSocket: {e}")
            pass
        
        return notification
    
    @staticmethod
    def create_project_invitation(recipient, project, sender):
        """
        Crée une notification d'invitation à rejoindre un projet
        
        Args:
            recipient: Utilisateur invité
            project: Projet auquel l'utilisateur est invité
            sender: Utilisateur qui envoie l'invitation
        """
        title = "Invitation to join a project"
        message = f"You have been invited to join the project « {project.name} » by {sender.username}."
        
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='PROJECT_INVITATION',  # Assurez-vous que ce type existe dans votre modèle
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id
        )
    @staticmethod
    def create_Leave_Request(recipient, project, sender):
        title = "Leave Request"
        message = f"{sender.username} woulde leave your project :  « {project.name} » ."
        
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='LEAVE_REQUEST',  # Assurez-vous que ce type existe dans votre modèle
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id
        )
    
    @staticmethod
    def create_membership_request(recipient, project, sender):
        title = "New membership application"
        
        sender_name = getattr(sender, 'full_name', None) or getattr(sender, 'username', None) or 'Unknown user'
        
        message = f"{sender_name} would like to join your project « {project.title} »."
        
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='MEMBERSHIP_REQUEST',
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id
        )
    
    @staticmethod
    def notify_group(users, notification_type, title, message, related_object=None, project_id=None, sender_id=None):
        """Envoie une notification à un groupe d'utilisateurs"""
        notifications = []
        for user in users:
            notification = NotificationService.create_notification(
                user, notification_type, title, message, related_object, project_id, sender_id
            )
            notifications.append(notification)
        return notifications
    
    @staticmethod
    def get_user_notifications(user, read=None, limit=None):
        """
        Récupère les notifications d'un utilisateur
        
        Args:
            user: Utilisateur dont on veut les notifications
            read: Si True, renvoie les notifications lues, si False les non lues, si None toutes
            limit: Nombre maximum de notifications à renvoyer
        """
        notifications = Notification.objects.filter(recipient=user)
        
        if read is not None:
            notifications = notifications.filter(read=read)
        
        notifications = notifications.order_by('-created_at')
        
        if limit:
            notifications = notifications[:limit]
        
        return notifications