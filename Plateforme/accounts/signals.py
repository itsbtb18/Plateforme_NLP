"""
Account signals - Sync user status with is_active flag.
When a user's status is set to 'blocked', automatically deactivate the account.
When reactivated, set is_active back to True.
Also: invalidate all sessions on password change.
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(pre_save, sender=User)
def sync_blocked_status(sender, instance, **kwargs):
    """
    Automatically sync is_active with status field:
    - status='blocked' → is_active=False
    - status='active' → is_active=True
    """
    if not instance.pk:
        return  # Skip new users (handled by registration flow)

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Only act if status actually changed
    if old_instance.status != instance.status:
        if instance.status == 'blocked':
            instance.is_active = False
            logger.info(f"User {instance.email} blocked → is_active set to False")
        elif instance.status == 'active' and old_instance.status == 'blocked':
            instance.is_active = True
            logger.info(f"User {instance.email} unblocked → is_active set to True")


def logout_all_sessions_on_password_change(sender, request, user, **kwargs):
    """
    Invalidate all other sessions when user changes password.
    Keep the current session active.
    """
    current_session_key = request.session.session_key
    
    # Delete all sessions for this user except the current one
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        try:
            data = session.get_decoded()
            if data.get('_auth_user_id') == str(user.pk):
                if session.session_key != current_session_key:
                    session.delete()
        except Exception:
            continue
    
    logger.info(f"All other sessions invalidated for user {user.email} after password change")


# Connect to allauth's password_changed signal
try:
    from allauth.account.signals import password_changed
    password_changed.connect(logout_all_sessions_on_password_change)
    logger.info("Password change session invalidation signal connected")
except ImportError:
    logger.warning("allauth not available, password change session invalidation not configured")
