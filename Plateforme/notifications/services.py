from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from typing import Optional
from .models import Notification


class NotificationService:
    @staticmethod
    def create_notification(
        recipient,
        notification_type,
        title,
        message,
        related_object=None,
        project_id=None,
        sender_id=None,
        action_url: Optional[str] = None,
    ):
        """
        Crée une notification et l'envoie via WebSocket si possible
        """
        notification = Notification(
            recipient=recipient,
            type=notification_type,
            title=title,
            message=message,
            project_id=project_id,
            sender_id=sender_id,
        )

        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            notification.content_type = content_type
            notification.object_id = related_object.id

        notification.save()

        channel_layer = get_channel_layer()
        user_group_name = f"user_{recipient.id}_notifications"

        notification_data = {
            'id': notification.id,
            'type': notification.get_type_display(),
            'title': notification.title,
            'message': notification.message,
            'created_at': notification.created_at.isoformat(),
            'project_id': str(notification.project_id) if notification.project_id else None,
            'sender_id': str(notification.sender_id) if notification.sender_id else None,
            'action_url': action_url,
        }

        try:
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(
                    user_group_name,
                    {
                        'type': 'notification_message',
                        'notification': notification_data,
                    },
                )
        except Exception as e:
            print(f"Erreur WebSocket: {e}")

        return notification

    @staticmethod
    def create_project_invitation(recipient, project, sender):
        title = _("Invitation to join a project")
        message = _("You have been invited to join the project %(project_name)s by %(sender_name)s.") % {
            'project_name': project.name,
            'sender_name': sender.username
        }
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='PROJECT_INVITATION',
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
        )

    @staticmethod
    def create_leave_request(recipient, project, sender):
        title = _("Leave Request")
        message = _("%(sender_name)s would like to leave your project %(project_name)s.") % {
            'sender_name': sender.username,
            'project_name': project.name
        }
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='LEAVE_REQUEST',
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
        )

    # Backwards compatibility
    create_Leave_Request = create_leave_request

    @staticmethod
    def create_membership_request(recipient, project, sender):
        title = _("New membership application")
        sender_name = getattr(sender, 'full_name', None) or getattr(sender, 'username', None) or _('Unknown user')
        message = _("%(sender_name)s would like to join your project %(project_title)s.") % {
            'sender_name': sender_name,
            'project_title': project.title
        }
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type='MEMBERSHIP_REQUEST',
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
        )

    @staticmethod
    def notify_group(users, notification_type, title, message, related_object=None, project_id=None, sender_id=None):
        notifications = []
        for user in users:
            notification = NotificationService.create_notification(
                user,
                notification_type,
                title,
                message,
                related_object,
                project_id,
                sender_id,
            )
            notifications.append(notification)
        return notifications

    @staticmethod
    def get_user_notifications(user, read=None, limit=None):
        notifications = Notification.objects.filter(recipient=user)
        if read is not None:
            notifications = notifications.filter(read=read)
        notifications = notifications.order_by('-created_at')
        if limit:
            notifications = notifications[:limit]
        return notifications
