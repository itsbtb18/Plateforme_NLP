from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from notifications.services import NotificationService

from events.models import Event, EventRegistration

User = get_user_model()


@receiver(post_save, sender=Event)
def notify_new_event(sender, instance, created, **kwargs):
    """Signal triggered when a new event is created"""
    if created and instance.approval_status == "approved" and instance.is_approved:
        active_users = User.objects.filter(is_active=True)

        NotificationService.notify_group(
            active_users,
            "EVENT_CREATED",
            _("New event: %(title)s") % {"title": instance.title},
            _("A new academic event has been announced: %(title)s, planned on %(date)s")
            % {"title": instance.title, "date": instance.start_date},
            instance,
        )


@receiver(post_save, sender=EventRegistration)
def notify_event_registration(sender, instance, created, **kwargs):
    """Signal triggered when a user registers for an event"""
    if created:
        event_organizer = instance.event.created_by

        NotificationService.create_notification(
            event_organizer,
            "MEMBERSHIP_REQUEST",
            _("New registration for your event"),
            _("%(user)s registered for your event: %(title)s")
            % {"user": instance.user.email, "title": instance.event.title},
            instance,
        )

        event_date = instance.event.start_date
        reminder_date = event_date - timedelta(days=1)

        if reminder_date > timezone.now().date():
            NotificationService.create_notification(
                instance.user,
                "EVENT_CREATED",
                _("Reminder: %(title)s tomorrow") % {"title": instance.event.title},
                _(
                    "Reminder: The event %(title)s which you are registered for is scheduled for tomorrow."
                )
                % {"title": instance.event.title},
                instance.event,
            )
