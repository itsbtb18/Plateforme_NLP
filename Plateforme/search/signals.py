from django.db.models.signals import post_delete
from django.dispatch import receiver
from django_elasticsearch_dsl.registries import registry
from resources.models import Course, NLPTool, Corpus, Document
from institutions.models import Institution
from projects.models import Project
from events.models import Event
from accounts.models import CustomUser

@receiver(post_delete, sender=Course)
@receiver(post_delete, sender=NLPTool)
@receiver(post_delete, sender=Corpus)
@receiver(post_delete, sender=Document)
@receiver(post_delete, sender=Institution)
@receiver(post_delete, sender=Project)
@receiver(post_delete, sender=Event)
@receiver(post_delete, sender=CustomUser)
def delete_document(sender, instance, **kwargs):
    registry.delete(instance)