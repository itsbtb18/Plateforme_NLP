"""
Utility functions for accessing global settings
"""
from django.core.cache import cache
from .models import GlobalSettings


def get_global_settings():
    """
    Get global settings instance with caching
    Cache is invalidated whenever settings are updated
    """
    cached_settings = cache.get('global_settings')
    if cached_settings is None:
        cached_settings = GlobalSettings.get_settings()
        cache.set('global_settings', cached_settings, timeout=3600)  # Cache for 1 hour
    return cached_settings


def invalidate_settings_cache():
    """Invalidate the settings cache"""
    cache.delete('global_settings')


def is_feature_enabled(feature_name):
    """
    Check if a specific feature is enabled
    
    Args:
        feature_name (str): The name of the feature flag attribute
        
    Returns:
        bool: True if feature is enabled, False otherwise
    """
    settings = get_global_settings()
    return getattr(settings, feature_name, False)


def is_maintenance_mode():
    """Check if the platform is in maintenance mode"""
    return get_global_settings().maintenance_mode


def get_site_name():
    """Get the site name"""
    return get_global_settings().site_name


def get_email_config():
    """Get email configuration as a dictionary"""
    settings = get_global_settings()
    return {
        'from_name': settings.email_from_name,
        'from_address': settings.email_from_address,
        'smtp_host': settings.smtp_host,
        'smtp_port': settings.smtp_port,
        'smtp_use_tls': settings.smtp_use_tls,
    }


# Feature flag convenience methods
def can_register_users():
    """Check if user registration is enabled"""
    return is_feature_enabled('enable_user_registration')


def social_login_enabled():
    """Check if social login is enabled"""
    return is_feature_enabled('enable_social_login')


def two_factor_auth_enabled():
    """Check if 2FA is enabled"""
    return is_feature_enabled('enable_two_factor_auth')


def forum_enabled():
    """Check if forum is enabled"""
    return is_feature_enabled('enable_forum')


def qa_enabled():
    """Check if Q&A is enabled"""
    return is_feature_enabled('enable_qa')


def events_enabled():
    """Check if events are enabled"""
    return is_feature_enabled('enable_events')


def projects_enabled():
    """Check if projects are enabled"""
    return is_feature_enabled('enable_projects')


def chatbot_enabled():
    """Check if chatbot is enabled"""
    return is_feature_enabled('enable_chatbot')


def resource_submission_enabled():
    """Check if resource submission is enabled"""
    return is_feature_enabled('enable_resource_submission')


def content_moderation_enabled():
    """Check if content moderation is enabled"""
    return is_feature_enabled('enable_content_moderation')
