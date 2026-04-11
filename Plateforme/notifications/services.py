import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override as translation_override

from .models import Notification

logger = logging.getLogger(__name__)


class LocalizedValue:
    """A value that has both English and Arabic versions.

    Use this when passing user names or other bilingual content to notifications.
    Example: LocalizedValue(en="John Doe", ar="جون دو")
    """

    def __init__(self, en: str, ar: str = None):
        self.en = en
        self.ar = ar if ar else en  # Fallback to English if no Arabic

    def __str__(self):
        return self.en  # Default to English if used as plain string

    @staticmethod
    def from_user(user):
        """Create LocalizedValue from a User object with bilingual names."""
        en = user.full_name_en or user.full_name or user.email
        ar = user.full_name_ar or user.full_name_en or user.full_name or user.email
        return LocalizedValue(en=en, ar=ar)


class NotificationService:
    @staticmethod
    def _resolve_kwargs_for_lang(kwargs: dict[str, Any], lang: str) -> dict[str, Any]:
        """Resolve kwargs for a specific language.

        If a value is a LocalizedValue, extract the appropriate language version.
        Otherwise, use the value as-is.
        """
        if not kwargs:
            return {}

        resolved = {}
        for key, value in kwargs.items():
            if isinstance(value, LocalizedValue):
                resolved[key] = value.ar if lang == "ar" else value.en
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _resolve_bilingual(title, message, title_kwargs=None, message_kwargs=None):
        """Resolve title/message into both English and Arabic strings.

        Works with lazy translation strings: evaluates them under each
        language override so both versions are stored in the database.
        For plain strings (no lazy proxy), the same value is used as fallback.

        Args:
            title: A lazy translation string (or plain string) for the title
            message: A lazy translation string (or plain string) for the message
            title_kwargs: Optional dict of format kwargs for title (applied after translation)
                         Values can be LocalizedValue for bilingual support
            message_kwargs: Optional dict of format kwargs for message (applied after translation)
                           Values can be LocalizedValue for bilingual support
        """
        title_kwargs = title_kwargs or {}
        message_kwargs = message_kwargs or {}

        try:
            with translation_override("en"):
                # For lazy strings, str() evaluates to English under 'en' override
                title_en = str(title)
                message_en = str(message)
                # Resolve kwargs for English language
                title_kwargs_en = NotificationService._resolve_kwargs_for_lang(
                    title_kwargs, "en"
                )
                message_kwargs_en = NotificationService._resolve_kwargs_for_lang(
                    message_kwargs, "en"
                )
                # Apply formatting if kwargs provided
                if title_kwargs_en:
                    title_en = title_en % title_kwargs_en
                if message_kwargs_en:
                    message_en = message_en % message_kwargs_en
        except Exception:
            title_en = str(title)
            message_en = str(message)

        try:
            with translation_override("ar"):
                # For lazy strings, str() evaluates to Arabic under 'ar' override
                title_ar = str(title)
                message_ar = str(message)
                # Resolve kwargs for Arabic language
                title_kwargs_ar = NotificationService._resolve_kwargs_for_lang(
                    title_kwargs, "ar"
                )
                message_kwargs_ar = NotificationService._resolve_kwargs_for_lang(
                    message_kwargs, "ar"
                )
                # Apply formatting if kwargs provided
                if title_kwargs_ar:
                    title_ar = title_ar % title_kwargs_ar
                if message_kwargs_ar:
                    message_ar = message_ar % message_kwargs_ar
        except Exception:
            title_ar = ""
            message_ar = ""

        # If Arabic resolved to same as English, it means no translation exists
        # Keep it anyway — the localized getter will fall back to English
        return title_en, title_ar, message_en, message_ar

    @staticmethod
    def create_notification(
        recipient,
        notification_type,
        title,
        message,
        related_object=None,
        project_id=None,
        sender_id=None,
        action_url: str | None = None,
        title_kwargs: dict[str, Any] | None = None,
        message_kwargs: dict[str, Any] | None = None,
    ):
        """
        Crée une notification et l'envoie via WebSocket si possible.
        Automatically stores both English and Arabic versions of
        title/message when lazy translation strings are passed.

        Args:
            title: A lazy translation string _("...") - DO NOT format before passing
            message: A lazy translation string _("...") - DO NOT format before passing
            title_kwargs: Dict of format kwargs for title, e.g. {'project': project.name}
            message_kwargs: Dict of format kwargs for message, e.g. {'user': user.name}
        """
        title_en, title_ar, message_en, message_ar = (
            NotificationService._resolve_bilingual(
                title, message, title_kwargs, message_kwargs
            )
        )

        notification = Notification(
            recipient=recipient,
            type=notification_type,
            title=title_en,  # legacy field gets English as default
            title_en=title_en,
            title_ar=title_ar,
            message=message_en,  # legacy field gets English as default
            message_en=message_en,
            message_ar=message_ar,
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
            "id": notification.id,
            "type": notification.get_type_display(),
            "title": notification.title_en,
            "title_en": notification.title_en,
            "title_ar": notification.title_ar,
            "message": notification.message_en,
            "message_en": notification.message_en,
            "message_ar": notification.message_ar,
            "created_at": notification.created_at.isoformat(),
            "project_id": str(notification.project_id)
            if notification.project_id
            else None,
            "sender_id": str(notification.sender_id)
            if notification.sender_id
            else None,
            "action_url": action_url,
        }

        try:
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(
                    user_group_name,
                    {
                        "type": "notification_message",
                        "notification": notification_data,
                    },
                )
        except Exception:
            logger.exception("WebSocket notification delivery failed")

        return notification

    @staticmethod
    def create_project_invitation(recipient, project, sender):
        title = _("Invitation to join a project")
        message = _(
            "You have been invited to join the project %(project_name)s by %(sender_name)s."
        )
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type="PROJECT_INVITATION",
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
            message_kwargs={
                "project_name": project.name,
                "sender_name": LocalizedValue.from_user(sender),
            },
        )

    @staticmethod
    def create_leave_request(recipient, project, sender):
        title = _("Leave Request")
        message = _(
            "%(sender_name)s would like to leave your project %(project_name)s."
        )
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type="LEAVE_REQUEST",
            title=title,
            message=message,
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
            message_kwargs={
                "sender_name": LocalizedValue.from_user(sender),
                "project_name": project.name,
            },
        )

    # Backwards compatibility
    create_Leave_Request = create_leave_request

    @staticmethod
    def create_membership_request(recipient, project, sender):
        title = _("New membership application")
        message = _(
            "%(sender_name)s would like to join your project %(project_title)s."
        )
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type="MEMBERSHIP_REQUEST",
            title=title,
            message=message,
            message_kwargs={
                "sender_name": LocalizedValue.from_user(sender),
                "project_title": project.title,
            },
            related_object=project,
            project_id=project.id,
            sender_id=sender.id,
        )

    @staticmethod
    def notify_group(
        users,
        notification_type,
        title,
        message,
        related_object=None,
        project_id=None,
        sender_id=None,
        title_kwargs=None,
        message_kwargs=None,
    ):
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
                title_kwargs=title_kwargs,
                message_kwargs=message_kwargs,
            )
            notifications.append(notification)
        return notifications

    @staticmethod
    def get_user_notifications(user, read=None, limit=None):
        notifications = Notification.objects.filter(recipient=user)
        if read is not None:
            notifications = notifications.filter(read=read)
        notifications = notifications.order_by("-created_at")
        if limit:
            notifications = notifications[:limit]
        return notifications
