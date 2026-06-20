from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from notifications.services import LocalizedValue, NotificationService
from resources.models import Corpus, Course, Document, NLPTool, ResourceBase

User = get_user_model()


@receiver(post_save, sender=Document)
@receiver(post_save, sender=Course)
@receiver(post_save, sender=Corpus)
@receiver(post_save, sender=NLPTool)
def notify_new_resource(sender, instance: ResourceBase, created: bool, **kwargs):
    """Notify staff when a new resource is created."""
    if not created:
        return

    admins = User.objects.filter(is_staff=True, is_active=True)
    if not admins.exists():
        return

    notification_type = "TOOL_ADDED" if isinstance(instance, NLPTool) else "RESOURCE_ADDED"

    NotificationService.notify_group(
        admins,
        notification_type,
        _("New resource: %(title)s"),
        _("A new resource has been added by %(author)s: %(title)s"),
        instance,
        title_kwargs={"title": instance.title},
        message_kwargs={
            "author": LocalizedValue.from_user(instance.author),
            "title": instance.title,
        },
    )


def notify_resource_contribution(sender, instance, created: bool, **kwargs):
    """
    Notify resource author when a contribution is created.

    This handler is generic and gets connected in apps.ready() only if a
    contribution model exists in the project.
    """
    if not created:
        return

    resource = getattr(instance, "resource", None)
    contributor = getattr(instance, "contributor", None)
    if resource is None or contributor is None:
        return

    resource_author = getattr(resource, "author", None)
    if resource_author is None or resource_author.pk == contributor.pk:
        return

    notification_type = "CORPUS_UPDATE" if isinstance(resource, Corpus) else "RESEARCH_UPDATE"

    NotificationService.create_notification(
        recipient=resource_author,
        notification_type=notification_type,
        title=_("New contribution to your resource"),
        message=_("%(contributor)s contributed to your resource: %(title)s"),
        related_object=instance,
        message_kwargs={
            "contributor": LocalizedValue.from_user(contributor),
            "title": getattr(resource, "title", ""),
        },
    )
