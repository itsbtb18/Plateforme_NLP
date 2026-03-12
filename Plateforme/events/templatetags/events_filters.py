"""
Custom template filters for Events app
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a variable key.
    Usage: {{ mydict|get_item:key_variable }}
    """
    if dictionary and hasattr(dictionary, 'get'):
        return dictionary.get(key)
    elif dictionary and hasattr(dictionary, '__getitem__'):
        try:
            return dictionary[key]
        except (KeyError, IndexError, TypeError):
            return None
    return None


@register.filter
def field_label(form, field_name):
    """
    Get the label of a form field.
    Usage: {{ form|field_label:field_name }}
    """
    if hasattr(form, 'fields') and field_name in form.fields:
        field = form.fields[field_name]
        return field.label if hasattr(field, 'label') and field.label else field_name
    return field_name
