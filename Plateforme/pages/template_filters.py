"""
Custom template filters for content rendering.
Provides easy access to parser functions in templates.
"""

from django import template
from pages.content_parser import extract_structured_content, extract_paper_metadata, linkify_text

register = template.Library()


@register.filter
def parse_research_content(content):
    """
    Template filter: parse raw content into structured research data.
    Usage: {{ post.content|parse_research_content }}
    
    Returns a dictionary with: title, authors, year, abstract, link
    """
    return extract_structured_content(content)


@register.filter
def extract_metadata(content):
    """
    Template filter: extract paper metadata for card preview.
    Usage: {% with metadata=post.content|extract_metadata %}
    
    Returns: {title, first_author, all_authors, year, abstract, link}
    """
    return extract_paper_metadata(content)


@register.filter
def make_links_clickable(text):
    """
    Template filter: convert plain URLs to clickable links.
    Usage: {{ post.content|make_links_clickable }}
    
    Converts https://... to <a href="...">
    """
    return linkify_text(text)
