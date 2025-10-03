from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from resources.models import Resource, ResourceContribution
from notifications.models import NotificationType
from notifications.services import NotificationService

@receiver(post_save, sender=Resource)
def notify_new_resource(sender, instance, created, **kwargs):
    """Signal déclenché quand une nouvelle ressource est créée"""
    if created:
        # Notifier les utilisateurs intéressés par ce type de ressource
        # Par exemple, on pourrait avoir un modèle UserInterest qui stocke les centres d'intérêt
        # interested_users = User.objects.filter(interests__resource_type=instance.resource_type)
        
        # Pour l'exemple, on notifie tous les administrateurs
        admins = User.objects.filter(is_staff=True)
        
        NotificationService.notify_group(
            admins,
            NotificationType.NEW_RESOURCE,
            f"New resource: {instance.title}",
            f"A new resource has been added by {instance.author.username}: {instance.title}",
            instance
        )

@receiver(post_save, sender=ResourceContribution)
def notify_resource_contribution(sender, instance, created, **kwargs):
    """Signal déclenché quand une contribution est apportée à une ressource"""
    if created:
        # Notifier l'auteur de la ressource
        resource_author = instance.resource.author
        
        if resource_author.id != instance.contributor.id:  # Ne pas notifier si l'auteur contribue à sa propre ressource
            NotificationService.create_notification(
                resource_author,
                NotificationType.CORPUS_UPDATE if instance.resource.resource_type == 'corpus' else NotificationType.RESEARCH_UPDATE,
                f"New contribution to your resource",
                f"{instance.contributor.username} contributed to your resource : {instance.resource.title}",
                instance
            )