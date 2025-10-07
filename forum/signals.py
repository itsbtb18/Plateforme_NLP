from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models import Q
from forum.models import ForumPost, ForumComment
from notifications.models import NotificationType
from notifications.services import NotificationService

@receiver(post_save, sender=ForumPost)
def notify_new_forum_post(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouveau post est créé dans le forum"""
    if created:
        # Notifier les administrateurs
        admins = User.objects.filter(is_staff=True)
        
        NotificationService.notify_group(
            admins, 
            NotificationType.NEW_FORUM_POST,
            f"New topic in the forum: {instance.title}",
            f"{instance.author.username} created a new topic in the forum: {instance.title}",
            instance
        )
        
        # Si le forum a des abonnés, on pourrait les notifier également
        # subscribers = ForumSubscription.objects.filter(forum=instance.forum).values_list('user', flat=True)
        # subscriber_users = User.objects.filter(id__in=subscribers).exclude(id=instance.author.id)
        # NotificationService.notify_group(subscriber_users, ...)

@receiver(post_save, sender=ForumComment)
def notify_new_comment(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouveau commentaire est créé sur un post du forum"""
    if created:
        # Notifier l'auteur du post
        post_author = instance.post.author
        
        if post_author.id != instance.author.id:  # Ne pas notifier si l'auteur commente son propre post
            NotificationService.create_notification(
                post_author,
                NotificationType.NEW_COMMENT,
                f"New comment on your topic",
                f"{instance.author.username} commented on your topic: {instance.post.title}",
                instance
            )
        
        # Notifier les autres participants à la discussion (qui ont déjà commenté)
        participants = ForumComment.objects.filter(post=instance.post) \
                                        .exclude(author=instance.author) \
                                        .exclude(author=post_author) \
                                        .values_list('author', flat=True) \
                                        .distinct()
        
        participant_users = User.objects.filter(id__in=participants)
        
        NotificationService.notify_group(
            participant_users,
            NotificationType.NEW_COMMENT,
            f"New comment in a discussion",
            f"{instance.author.username} commented on the topic: {instance.post.title}",
            instance
        )