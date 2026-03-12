"""
Template tags for accessing global settings
"""
from django import template
from settings.utils import (
    get_global_settings,
    is_feature_enabled,
    is_maintenance_mode,
    get_site_name
)

register = template.Library()


@register.simple_tag
def get_setting(setting_name):
    """
    Get a specific setting value
    Usage: {% get_setting 'site_name' %}
    """
    settings = get_global_settings()
    return getattr(settings, setting_name, None)


@register.simple_tag
def setting(setting_name):
    """
    Alias for get_setting for convenience
    Usage: {% setting 'site_name' %}
    """
    return get_setting(setting_name)


@register.filter
def is_feature_enabled_filter(feature_name):
    """
    Check if a feature is enabled (filter version)
    Usage: {{ 'enable_forum'|is_feature_enabled }}
    """
    return is_feature_enabled(feature_name)


@register.simple_tag
def feature_enabled(feature_name):
    """
    Check if a feature is enabled (simple tag version)
    Usage: {% feature_enabled 'enable_forum' as forum_is_enabled %}
    """
    return is_feature_enabled(feature_name)


@register.simple_tag
def global_settings():
    """
    Get the entire global settings object
    Usage: {% global_settings as settings %}
    """
    return get_global_settings()


@register.simple_tag
def maintenance_mode():
    """
    Check if maintenance mode is enabled
    Usage: {% maintenance_mode as is_maintenance %}
    """
    return is_maintenance_mode()


@register.simple_tag
def site_name():
    """
    Get the site name
    Usage: {% site_name as name %}
    """
    return get_site_name()


# Convenience tags for common features
@register.simple_tag
def forum_enabled():
    """Check if forum is enabled"""
    return is_feature_enabled('enable_forum')


@register.simple_tag
def qa_enabled():
    """Check if Q&A is enabled"""
    return is_feature_enabled('enable_qa')


@register.simple_tag
def events_enabled():
    """Check if events are enabled"""
    return is_feature_enabled('enable_events')


@register.simple_tag
def projects_enabled():
    """Check if projects are enabled"""
    return is_feature_enabled('enable_projects')


@register.simple_tag
def chatbot_enabled():
    """Check if chatbot is enabled"""
    return is_feature_enabled('enable_chatbot')


@register.simple_tag
def registration_enabled():
    """Check if user registration is enabled"""
    return is_feature_enabled('enable_user_registration')
