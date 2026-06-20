"""
Template tags and filters for dynamic content localization (AR/EN).

Usage in templates:
    {% load localization_tags %}
    
    {# Using the filter - returns localized field value #}
    {{ object|localized:'title' }}
    {{ object|localized:'description' }}
    {{ user|localized:'full_name' }}
    
    {# Using the tag - assigns to a variable #}
    {% get_localized object 'title' as localized_title %}
    {{ localized_title }}
    
    {# Check current language #}
    {% if is_rtl %}
        <div dir="rtl">...</div>
    {% endif %}
"""

from django import template
from django.utils.translation import get_language

register = template.Library()


def get_current_language_code():
    """Get the current language code, defaulting to 'en'."""
    lang = get_language()
    if lang:
        # Handle cases like 'ar-dz' -> 'ar'
        return lang.split('-')[0].lower()
    return 'en'


@register.filter(name='localized')
def localized_field(obj, field_name):
    """
    Filter to get the localized version of a field.
    
    Usage: {{ object|localized:'title' }}
    
    This will return:
    - object.title_ar if current language is Arabic
    - object.title_en if current language is English
    - Falls back to object.title_en -> object.title_ar -> object.title
    """
    if obj is None:
        return ''
    
    lang_code = get_current_language_code()
    
    # Try localized field first (e.g., title_ar or title_en)
    localized_field_name = f"{field_name}_{lang_code}"
    value = getattr(obj, localized_field_name, None)
    
    if value:
        return value
    
    # Fallback chain: try the other language, then the base field
    fallback_lang = 'ar' if lang_code == 'en' else 'en'
    fallback_field_name = f"{field_name}_{fallback_lang}"
    fallback_value = getattr(obj, fallback_field_name, None)
    
    if fallback_value:
        return fallback_value
    
    # Final fallback: try the base field name
    base_value = getattr(obj, field_name, None)
    return base_value if base_value else ''


@register.simple_tag(takes_context=True)
def get_localized(context, obj, field_name):
    """
    Tag to get localized field and optionally assign to variable.
    
    Usage: 
        {% get_localized object 'title' as localized_title %}
        {{ localized_title }}
    """
    return localized_field(obj, field_name)


@register.simple_tag(takes_context=True)
def is_rtl(context):
    """
    Check if the current language is RTL (Arabic).
    
    Usage:
        {% is_rtl as rtl %}
        {% if rtl %}<div dir="rtl">{% endif %}
    """
    lang_code = get_current_language_code()
    return lang_code == 'ar'


@register.simple_tag
def current_lang():
    """
    Get the current language code.
    
    Usage: {% current_lang as lang %}
    """
    return get_current_language_code()


@register.filter(name='dir_attr')
def direction_attribute(obj):
    """
    Return 'rtl' or 'ltr' based on current language.
    
    Usage: <div dir="{{ obj|dir_attr }}">
    """
    lang_code = get_current_language_code()
    return 'rtl' if lang_code == 'ar' else 'ltr'


@register.inclusion_tag('resources/includes/localized_text.html', takes_context=True)
def render_localized(context, obj, field_name, tag='p', css_class=''):
    """
    Render a localized field with proper RTL/LTR direction.
    
    Usage: {% render_localized object 'description' tag='div' css_class='lead' %}
    """
    lang_code = get_current_language_code()
    value = localized_field(obj, field_name)
    direction = 'rtl' if lang_code == 'ar' else 'ltr'
    
    return {
        'value': value,
        'tag': tag,
        'css_class': css_class,
        'direction': direction,
        'lang': lang_code,
    }


@register.filter(name='localized_or')
def localized_field_or_default(obj, args):
    """
    Get localized field with a default value.
    
    Usage: {{ object|localized_or:'title,No title available' }}
    """
    if ',' not in args:
        return localized_field(obj, args)
    
    field_name, default = args.split(',', 1)
    value = localized_field(obj, field_name.strip())
    return value if value else default.strip()


# Approval status display helpers
@register.filter(name='status_badge')
def approval_status_badge(status):
    """
    Return Bootstrap badge class for approval status.
    
    Usage: <span class="badge {{ object.approval_status|status_badge }}">
    """
    badges = {
        'pending': 'bg-warning text-dark',
        'approved': 'bg-success',
        'rejected': 'bg-danger',
    }
    return badges.get(status, 'bg-secondary')


@register.filter(name='status_icon')
def approval_status_icon(status):
    """
    Return icon class for approval status.
    
    Usage: <i class="{{ object.approval_status|status_icon }}"></i>
    """
    icons = {
        'pending': 'bi bi-clock',
        'approved': 'bi bi-check-circle',
        'rejected': 'bi bi-x-circle',
    }
    return icons.get(status, 'bi bi-question-circle')


@register.simple_tag(takes_context=True)
def can_view_resource(context, obj):
    """
    Check if the current user can view a resource based on approval status.
    
    Usage:
        {% can_view_resource object as can_view %}
        {% if can_view %}...{% endif %}
    """
    request = context.get('request')
    if not request:
        return False
    
    user = request.user
    
    # Staff can always view
    if user.is_staff:
        return True
    
    # Check approval status
    approval_status = getattr(obj, 'approval_status', None)
    if approval_status == 'approved':
        return True
    
    # Check if user is the creator/owner
    created_by = getattr(obj, 'created_by', None)
    contributor = getattr(obj, 'contributor', None)
    coordinator = getattr(obj, 'coordinator', None)
    creator = getattr(obj, 'creator', None)
    
    if user.is_authenticated:
        if created_by and created_by == user:
            return True
        if contributor and contributor == user:
            return True
        if coordinator and coordinator == user:
            return True
        if creator and creator == user:
            return True
    
    return False
