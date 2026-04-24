from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from forum.rendering import render_message_markdown

register = template.Library()


@register.filter(name="render_message")
def render_message(value: str) -> str:
    """
    Template filter: markdown -> sanitized HTML.
    """
    return mark_safe(render_message_markdown(value or ""))

