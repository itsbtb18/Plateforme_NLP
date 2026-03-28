"""
Account signals.
- Sync user status with is_active flag.
- Auto-create UserProfile on user creation.
- Invalidate all other sessions on password change.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import UserProfile

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(pre_save, sender=User)
def sync_blocked_status(sender, instance, **kwargs):
    """
    Automatically sync is_active with status field:
    - status='blocked' -> is_active=False
    - status='active' -> is_active=True
    """
    if not instance.pk:
        return  # Skip new users (handled by registration flow)

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.status != instance.status:
        if instance.status == "blocked":
            instance.is_active = False
            logger.info("User %s blocked -> is_active=False", instance.email)
        elif instance.status == "active" and old_instance.status == "blocked":
            instance.is_active = True
            logger.info("User %s unblocked -> is_active=True", instance.email)


@receiver(post_save, sender=User)
def auto_create_user_profile(sender, instance, created, **kwargs):
    """
    Create UserProfile automatically for each newly created user.
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)


def logout_all_sessions_on_password_change(sender, request, user, **kwargs):
    """
    Invalidate all other sessions when user changes password.
    Keep the current session active.
    """
    current_session_key = request.session.session_key

    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        try:
            data = session.get_decoded()
            if (
                data.get("_auth_user_id") == str(user.pk)
                and session.session_key != current_session_key
            ):
                session.delete()
        except Exception:
            continue

    logger.info(
        "All other sessions invalidated for user %s after password change", user.email
    )


try:
    from allauth.account.signals import password_changed

    password_changed.connect(logout_all_sessions_on_password_change)
    logger.info("Password change session invalidation signal connected")
except ImportError:
    logger.warning(
        "allauth not available, password change session invalidation not configured"
    )
