"""Custom template tags and filters for the projects app."""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.
    Usage: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None:
        return None
    return dictionary.get(str(key))


@register.filter
def highlight_title(project, highlights):
    """
    Get highlighted title for a project if available.
    Usage: {{ project|highlight_title:highlights }}
    """
    if not highlights:
        return project.get_localized_title()
    
    project_highlights = highlights.get(str(project.pk), {})
    if 'title' in project_highlights:
        return project_highlights['title']
    return project.get_localized_title()


@register.filter
def highlight_description(project, highlights):
    """
    Get highlighted description for a project if available.
    Usage: {{ project|highlight_description:highlights }}
    """
    if not highlights:
        desc = project.get_localized_description()
        if len(desc) > 150:
            return desc[:150] + '...'
        return desc
    
    project_highlights = highlights.get(str(project.pk), {})
    if 'description' in project_highlights:
        return project_highlights['description']
    
    desc = project.get_localized_description()
    if len(desc) > 150:
        return desc[:150] + '...'
    return desc
