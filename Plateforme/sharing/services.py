"""
Share service layer – keeps views thin.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.db import IntegrityError

from .models import Share, ShareReply


# Map of short names used in templates → model app_label.model_name pairs
CONTENT_TYPE_MAP = {
    # key used in templates / JS
    'tool': ('resources', 'tool'),
    'corpus': ('resources', 'corpus'),
    'course': ('resources', 'course'),
    'resource': ('resources', 'resource'),
    'institution': ('institutions', 'institution'),
    'project': ('projects', 'project'),
    'topic': ('forum', 'topic'),
    'event': ('events', 'event'),
    'post': ('QA', 'post'),          # news / blog post
}


def _resolve_content_type(content_type_str: str) -> ContentType:
    """Look up the ContentType from our short-name map."""
    key = content_type_str.lower()
    if key not in CONTENT_TYPE_MAP:
        raise ValueError(f"Unknown content type: {content_type_str!r}")
    app_label, model = CONTENT_TYPE_MAP[key]
    return ContentType.objects.get(app_label=app_label, model=model)


def _get_title(obj) -> str:
    """Best-effort title extraction from any platform object."""
    for attr in ('get_localized_title', 'title', 'name', '__str__'):
        val = getattr(obj, attr, None)
        if val is None:
            continue
        result = val() if callable(val) else val
        if result:
            return str(result)
    return ''


def _get_url(obj) -> str:
    try:
        return obj.get_absolute_url()
    except Exception:
        return ''


class ShareService:
    @staticmethod
    def create_share(sender, receiver, content_type_str: str, object_id: str, message: str = ''):
        """
        Create a Share and fire a notification.
        Returns (share, created:bool).
        """
        ct = _resolve_content_type(content_type_str)

        # Snapshot title + URL at share time so they survive object deletion
        try:
            obj = ct.get_object_for_this_type(pk=object_id)
            title = _get_title(obj)
            url = _get_url(obj)
        except Exception:
            obj = None
            title = ''
            url = ''

        try:
            share = Share.objects.create(
                sender=sender,
                receiver=receiver,
                content_type=ct,
                object_id=object_id,
                content_title=title,
                content_url=url,
                message=message,
                status=Share.Status.SENT,
            )
            created = True
        except IntegrityError:
            share = Share.objects.get(
                sender=sender,
                receiver=receiver,
                content_type=ct,
                object_id=object_id,
            )
            created = False

        if created:
            ShareService._notify_receiver(share, sender, receiver, title)

        return share, created

    @staticmethod
    def _notify_receiver(share, sender, receiver, title):
        """Send a Django-Channels notification to the receiver."""
        try:
            from notifications.services import NotificationService, LocalizedValue
            sender_name = LocalizedValue.from_user(sender)
            NotificationService.create_notification(
                recipient=receiver,
                notification_type='MESSAGE',
                title=_("%(name)s shared something with you") % {'name': sender.full_name or sender.email},
                message=_("%(name)s shared '%(title)s' with you.") % {
                    'name': sender.full_name or sender.email,
                    'title': title or _('an item'),
                },
                related_url=f"/sharing/inbox/",
            )
        except Exception:
            pass  # Notification failure must never block the share itself

    @staticmethod
    def notify_reply(reply: ShareReply, other_user):
        """Notify the other party when a reply is posted."""
        try:
            from notifications.services import NotificationService
            NotificationService.create_notification(
                recipient=other_user,
                notification_type='MESSAGE',
                title=_("New reply on a shared item"),
                message=_("%(name)s replied on a share: %(snippet)s") % {
                    'name': reply.author.full_name or reply.author.email,
                    'snippet': reply.content[:80],
                },
                related_url=f"/sharing/thread/{reply.share_id}/",
            )
        except Exception:
            pass
