from django.db.models.signals import post_save
from django.dispatch import receiver
from projects.models import Project
from .models import ProjectChat


@receiver(post_save, sender=Project)
def create_project_chatroom(sender, instance, created, **kwargs):
    """
    Automatically create a chatroom when a project is created.
    """
    if created:
        ProjectChat.objects.get_or_create(project=instance)
