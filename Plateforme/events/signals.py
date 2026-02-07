from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from events.models import AcademicEvent, EventRegistration
from notifications.models import NotificationType
from notifications.services import NotificationService

@receiver(post_save, sender=AcademicEvent)
def notify_new_academic_event(sender, instance, created, **kwargs):
    """Signal déclenché quand un nouvel événement académique est créé"""
    if created:
        active_users = User.objects.filter(is_active=True)
        
        NotificationService.notify_group(
            active_users,
            NotificationType.EVENT_REMINDER,
            _("New event: %(title)s") % {'title': instance.title},
            _("A new academic event has been announced: %(title)s, planned on %(date)s") % {'title': instance.title, 'date': instance.date},
            instance
        )

@receiver(post_save, sender=EventRegistration)
def notify_event_registration(sender, instance, created, **kwargs):
    """Signal déclenché quand un utilisateur s'inscrit à un événement"""
    if created:
        event_organizer = instance.event.organizer
        
        NotificationService.create_notification(
            event_organizer,
            NotificationType.MEMBERSHIP_REQUEST,
            _("New registration for your event"),
            _("%(username)s registered for your event: %(title)s") % {'username': instance.user.username, 'title': instance.event.title},
            instance
        )
        
        event_date = instance.event.date
        reminder_date = event_date - timedelta(days=1)
        
        if reminder_date > timezone.now().date():
            NotificationService.create_notification(
                instance.user,
                NotificationType.EVENT_REMINDER,
                _("Reminder: %(title)s tomorrow") % {'title': instance.event.title},
                _("Reminder: The event %(title)s which you are registered for is scheduled for tomorrow.") % {'title': instance.event.title},
                instance.event
            )