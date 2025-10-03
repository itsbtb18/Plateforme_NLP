from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from events.models import AcademicEvent, EventRegistration
from notifications.models import NotificationType
from notifications.services import NotificationService

@receiver(post_save, sender=AcademicEvent)
def notify_new_academic_event(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouvel événement académique est créé"""
    if created:
        # Notifier tous les utilisateurs (ou un groupe spécifique)
        # Pour l'exemple, on notifie tous les utilisateurs actifs
        active_users = User.objects.filter(is_active=True)
        
        NotificationService.notify_group(
            active_users,
            NotificationType.EVENT_REMINDER,
            f"New event: {instance.title}",
            f"A new academic event has been announced: {instance.title}, planned on {instance.date}",
            instance
        )

@receiver(post_save, sender=EventRegistration)
def notify_event_registration(sender, instance, created, **kwargs):
    """Signal déclenché quand un utilisateur s'inscrit à un événement"""
    if created:
        # Notifier l'organisateur de l'événement
        event_organizer = instance.event.organizer
        
        NotificationService.create_notification(
            event_organizer,
            NotificationType.MEMBERSHIP_REQUEST,
            f"New registration for your event",
            f"{instance.user.username} registered for your event: {instance.event.title}",
            instance
        )
        
        # Programmer un rappel pour l'utilisateur inscrit (1 jour avant l'événement)
        event_date = instance.event.date
        reminder_date = event_date - timedelta(days=1)
        
        # Dans un vrai projet, cette notification serait programmée avec Celery ou Django Q
        # Pour l'exemple, on l'enregistre juste avec une date future
        if reminder_date > timezone.now().date():
            NotificationService.create_notification(
                instance.user,
                NotificationType.EVENT_REMINDER,
                f"Reminder: {instance.event.title} tomorrow",
                f"Reminder: The event {instance.event.title} which you are registered for is scheduled for tomorrow.",
                instance.event
            )