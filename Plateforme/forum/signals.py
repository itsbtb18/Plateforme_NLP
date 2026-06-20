from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from forum.models import Topic, ChatRoom, Message
from notifications.models import Notification
from notifications.services import NotificationService

User = get_user_model()


@receiver(post_save, sender=Topic)
def notify_new_forum_topic(sender, instance, created, **kwargs):
    """Signal triggered when a new topic is created in the forum"""
    if created:
        admins = User.objects.filter(is_staff=True)
        
        NotificationService.notify_group(
            admins, 
            'FORUM_TOPIC',
            _("New topic in the forum: %(title)s") % {'title': instance.title},
            _("%(user)s created a new topic in the forum: %(title)s") % {'user': instance.creator.email, 'title': instance.title},
            instance
        )


@receiver(post_save, sender=Message)
def notify_new_message(sender, instance, created, **kwargs):
    """Signal triggered when a new message is created in a chatroom"""
    if created and instance.chatroom and instance.chatroom.topic:
        topic_creator = instance.chatroom.topic.creator
        
        if topic_creator.id != instance.user.id:
            NotificationService.create_notification(
                topic_creator,
                'FORUM_TOPIC',
                _("New message in your topic"),
                _("%(user)s posted a message in a chatroom related to your topic: %(title)s") % {'user': instance.user.email, 'title': instance.chatroom.topic.title},
                instance
            )