from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from forum.models import ForumPost, ForumComment
from notifications.models import NotificationType
from notifications.services import NotificationService

@receiver(post_save, sender=ForumPost)
def notify_new_forum_post(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouveau post est créé dans le forum"""
    if created:
        admins = User.objects.filter(is_staff=True)
        
        NotificationService.notify_group(
            admins, 
            NotificationType.NEW_FORUM_POST,
            _("New topic in the forum: %(title)s") % {'title': instance.title},
            _("%(username)s created a new topic in the forum: %(title)s") % {'username': instance.author.username, 'title': instance.title},
            instance
        )

@receiver(post_save, sender=ForumComment)
def notify_new_comment(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouveau commentaire est créé sur un post du forum"""
    if created:
        post_author = instance.post.author
        
        if post_author.id != instance.author.id:
            NotificationService.create_notification(
                post_author,
                NotificationType.NEW_COMMENT,
                _("New comment on your topic"),
                _("%(username)s commented on your topic: %(title)s") % {'username': instance.author.username, 'title': instance.post.title},
                instance
            )
        
        participants = ForumComment.objects.filter(post=instance.post) \
                                        .exclude(author=instance.author) \
                                        .exclude(author=post_author) \
                                        .values_list('author', flat=True) \
                                        .distinct()
        
        participant_users = User.objects.filter(id__in=participants)
        
        NotificationService.notify_group(
            participant_users,
            NotificationType.NEW_COMMENT,
            _("New comment in a discussion"),
            _("%(username)s commented on the topic: %(title)s") % {'username': instance.author.username, 'title': instance.post.title},
            instance
        )