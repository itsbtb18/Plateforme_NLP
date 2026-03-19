"""
Content parsing utilities for extracting structured data from scraped research/news content.
Handles markdown-like syntax and URLs.
"""

import re
from typing import Dict, Optional, List
from urllib.parse import urlparse


def extract_structured_content(content: str) -> Dict[str, Optional[str]]:
    """
    Parse raw scraped content into structured research paper/news card data.
    
    Handles English patterns: **Authors:**, **Year:**, **Abstract:**, etc.
    Handles Arabic patterns: المؤلفون، السنة، الملخص، العنوان
    [Read the full paper](https://...)
    
    Args:
        content (str): Raw content string
        
    Returns:
        Dict with keys: title, authors, year, abstract, link, raw_content
    """
    if not content:
        return {
            'title': None,
            'authors': None,
            'year': None,
            'abstract': None,
            'link': None,
            'raw_content': None,
        }
    
    result = {
        'title': None,
        'authors': None,
        'year': None,
        'abstract': None,
        'link': None,
        'raw_content': content,
    }
    
    # English: **Authors:** text OR Authors: text
    authors_match = re.search(
        r'(?:\*\*\s*)?Authors?\s*:\s*(?:\*\*\s*)?(.+?)(?=\n\s*(?:\*\*\s*)?(?:Year|Title|Abstract)\s*:|\n\s*\[|$)',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if authors_match:
        result['authors'] = authors_match.group(1).strip()
    
    # Arabic: المؤلفون or المؤلفون:
    if not result['authors']:
        ar_authors = re.search(
            r'(?:\*\*\s*)?(?:المؤلفون?|الكاتب)\s*[:\s]*(?:\*\*\s*)?(.+?)(?=\n\s*(?:\*\*\s*)?(?:السنة|العنوان|الملخص)\s*[:\s]|\n\s*\[|$)',
            content,
            re.DOTALL,
        )
        if ar_authors:
            result['authors'] = ar_authors.group(1).strip()
    
    # Year: English
    year_match = re.search(r'(?:\*\*\s*)?Year\s*:\s*(?:\*\*\s*)?(\d{4})', content, re.IGNORECASE)
    if year_match:
        result['year'] = year_match.group(1).strip()
    
    # Year: Arabic السنة
    if not result['year']:
        ar_year = re.search(r'(?:\*\*\s*)?السنة\s*[:\s]*(?:\*\*\s*)?(\d{4})', content)
        if ar_year:
            result['year'] = ar_year.group(1).strip()
    
    # Title: English
    title_match = re.search(
        r'(?:\*\*\s*)?Title\s*:\s*(?:\*\*\s*)?(.+?)(?=\n\s*(?:\*\*\s*)?(?:Authors?|Year|Abstract)\s*:|\n\s*\[|$)',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        result['title'] = title_match.group(1).strip()
    
    # Title: Arabic العنوان
    if not result['title']:
        ar_title = re.search(
            r'(?:\*\*\s*)?العنوان\s*[:\s]*(?:\*\*\s*)?(.+?)(?=\n\s*(?:\*\*\s*)?(?:المؤلفون?|السنة|الملخص)\s*[:\s]|\n\s*\[|$)',
            content,
            re.DOTALL,
        )
        if ar_title:
            result['title'] = ar_title.group(1).strip()
    
    # Abstract: English
    abstract_match = re.search(
        r'(?:\*\*\s*)?Abstract\s*:\s*(?:\*\*\s*)?(.+?)(?=\n\s*\[|$)',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if abstract_match:
        abstract_text = abstract_match.group(1).strip()
        abstract_text = re.sub(r'\n\s*(?:\*\*\s*)?(?:Authors?|Year|Title)\s*:.*$', '', abstract_text, flags=re.IGNORECASE | re.DOTALL).strip()
        result['abstract'] = abstract_text
    
    # Abstract: Arabic الملخص
    if not result['abstract']:
        ar_abstract = re.search(
            r'(?:\*\*\s*)?الملخص\s*[:\s]*(?:\*\*\s*)?(.+?)(?=\n\s*\[|$)',
            content,
            re.DOTALL,
        )
        if ar_abstract:
            result['abstract'] = ar_abstract.group(1).strip()
    
    # Fallback: plain text - use first line as title if short, rest as abstract
    if not result['title'] and not result['abstract'] and content.strip():
        lines = [ln.strip() for ln in content.split('\n') if ln.strip()]
        if lines:
            result['abstract'] = '\n'.join(lines)
            if len(lines[0]) < 150:  # First line looks like a title
                result['title'] = lines[0]
                result['abstract'] = '\n'.join(lines[1:]) if len(lines) > 1 else (lines[0] if len(lines) == 1 else '')
    
    # Extract URLs
    url_patterns = [
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'(https?://[^\s\[\]]+)',
    ]
    for pattern in url_patterns:
        url_match = re.search(pattern, content)
        if url_match:
            result['link'] = url_match.group(2) if len(url_match.groups()) == 2 else url_match.group(1)
            break
    
    return result


def parse_content_sections(content: str) -> List[Dict[str, str]]:
    """
    Parse content into sections for display.
    Useful for rendering in accordion or tab format.
    
    Args:
        content (str): Raw content string
        
    Returns:
        List of dicts with 'title' and 'content' keys
    """
    sections = []
    
    # Find all **SectionTitle:** patterns
    pattern = r'\*\*([^:]+):\*\*(.*?)(?=\*\*[^:]+:\*\*|$)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        section_title = match.group(1).strip()
        section_content = match.group(2).strip()
        
        if section_content:  # Only add non-empty sections
            sections.append({
                'title': section_title,
                'content': section_content
            })
    
    return sections


def sanitize_url(url: str) -> str:
    """
    Basic URL sanitization to prevent XSS.
    
    Args:
        url (str): URL to sanitize
        
    Returns:
        str: Sanitized URL or empty string if invalid
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme in ('http', 'https'):
            return url
    except:
        pass
    return ''


def linkify_text(text: str) -> str:
    """
    Convert plain URLs in text to clickable links.
    
    Args:
        text (str): Text to linkify
        
    Returns:
        str: HTML with clickable links
    """
    # Pattern for detecting URLs
    url_pattern = r'(https?://[^\s\[\]<>]+)'
    
    def replace_url(match):
        url = match.group(1)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="text-link">{url}</a>'
    
    return re.sub(url_pattern, replace_url, text)


def extract_paper_metadata(content: str, max_abstract_length: Optional[int] = 600) -> Dict[str, Optional[str]]:
    """
    Higher-level function to extract paper/research metadata.
    Returns title, first author, year, and abstract.
    
    Args:
        content (str): Raw content string
        max_abstract_length: Max chars for abstract (None = no truncation)
        
    Returns:
        Dict with metadata suitable for card display
    """
    structured = extract_structured_content(content)
    
    # Extract first author name only
    first_author = None
    if structured['authors']:
        authors = structured['authors'].split(',')
        first_author = authors[0].strip() if authors else None
    
    abstract = structured['abstract']
    if abstract and max_abstract_length and len(abstract) > max_abstract_length:
        abstract = abstract[: max_abstract_length - 3] + '...'
    
    return {
        'title': structured['title'],
        'first_author': first_author,
        'all_authors': structured['authors'],
        'year': structured['year'],
        'abstract': abstract,
        'link': structured['link'],
    }
