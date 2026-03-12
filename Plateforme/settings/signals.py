"""
Signal handlers for the settings app
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


def invalidate_cache_on_settings_change(sender, instance, created, **kwargs):
    """
    Invalidate settings cache whenever GlobalSettings is updated
    This ensures changes are reflected immediately across the app
    """
    try:
        from django.core.cache import cache
        cache.delete('global_settings')
    except Exception:
        pass


def connect_signals():
    """Register signal handlers"""
    from .models import GlobalSettings
    post_save.connect(invalidate_cache_on_settings_change, sender=GlobalSettings)
