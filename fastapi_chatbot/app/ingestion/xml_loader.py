"""
XML (JATS) parser for academic papers.

Extracts body text from NLM/JATS XML documents (common in academic
publishing), filters out references/acknowledgments/appendix, and
chunks by section with the same contract as pdf_loader.
"""

import re
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from langdetect import detect

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
MIN_CHUNK_TOKENS = 50

_SKIP_SECTION_TYPES = {
    "ref-list", "ack", "acknowledgments", "acknowledgements",
    "appendix", "supplementary-material", "glossary",
    "author-notes", "funding-group", "conflict",
}

_SKIP_TITLE_PATTERNS = re.compile(
    r"^\s*("
    r"references|bibliography|"
    r"acknowledgments?|acknowledgements?|"
    r"appendix|appendices|"
    r"conflict.{0,5}of.{0,5}interest|"
    r"funding|author.{0,5}contributions?|"
    r"data.{0,5}availability|supplementary"
    r")\s*$",
    re.IGNORECASE,
)

# Inline citation patterns
_CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[,;\s]+\d+)*\]"),
    re.compile(
        r"\(\w+(?:\s+et\s+al\.?)?,?\s*\d{4}"
        r"(?:[;,]\s*\w+(?:\s+et\s+al\.?)?,?\s*\d{4})*\)"
    ),
]


def load_and_chunk_xml(
    xml_path: str | Path,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
) -> Dict:
    """Parse a JATS XML file, extract sections, chunk.

    Returns same structure as pdf_loader.load_and_chunk_pdf.
    """
    xml_path = Path(xml_path)
    logger.info("Loading XML: %s", xml_path.name)

    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    # Strip namespace prefixes for easier traversal
    _strip_ns(root)

    title = _extract_xml_title(root, xml_path)
    abstract = _extract_abstract(root)

    # Extract body sections
    sections = _extract_body_sections(root)

    # Build chunks
    chunks: List[Dict] = []

    # Abstract as first chunk
    if abstract and len(abstract) // _CHARS_PER_TOKEN >= MIN_CHUNK_TOKENS:
        chunks.append({
            "index": 0,
            "heading": "Abstract",
            "content": abstract,
            "token_est": len(abstract) // _CHARS_PER_TOKEN,
        })

    # Section-based chunking
    for section_title, section_text in sections:
        section_text = _strip_citations(section_text)
        section_text = _clean_ws(section_text)

        if not section_text or len(section_text) // _CHARS_PER_TOKEN < MIN_CHUNK_TOKENS:
            continue

        token_est = len(section_text) // _CHARS_PER_TOKEN

        if token_est <= max_tokens:
            chunks.append({
                "index": len(chunks),
                "heading": section_title,
                "content": section_text,
                "token_est": token_est,
            })
        else:
            # Split large sections with sliding window
            sub_chunks = _sliding_window(section_text, max_tokens, overlap_tokens)
            for sc in sub_chunks:
                sc["heading"] = section_title
                sc["index"] = len(chunks)
                chunks.append(sc)

    # Detect language
    sample = " ".join(c["content"][:500] for c in chunks[:3])
    language = _detect_language(sample)

    logger.info("XML done: title='%s', chunks=%d, lang=%s", title, len(chunks), language)
    return {"title": title, "language": language, "chunks": chunks}


# ------------------------------------------------------------------
# XML extraction helpers
# ------------------------------------------------------------------

def _strip_ns(elem):
    """Remove XML namespace prefixes in-place for easier traversal."""
    if elem.tag and "}" in elem.tag:
        elem.tag = elem.tag.split("}", 1)[1]
    for child in elem:
        _strip_ns(child)


def _extract_xml_title(root, xml_path: Path) -> str:
    """Extract article title from JATS front matter."""
    for title_el in root.iter("article-title"):
        text = _elem_text(title_el).strip()
        if text:
            return text
    return xml_path.stem


def _extract_abstract(root) -> Optional[str]:
    """Extract abstract text."""
    for abstract_el in root.iter("abstract"):
        text = _elem_text(abstract_el).strip()
        if text:
            return text
    return None


def _extract_body_sections(root) -> List[tuple]:
    """Extract (section_title, section_text) pairs from <body>."""
    body = root.find(".//body")
    if body is None:
        return []

    sections = []
    for sec in body.findall("sec"):
        _extract_sec_recursive(sec, sections)

    return sections


def _extract_sec_recursive(sec_elem, sections: List[tuple]):
    """Recursively extract sections, skipping reference-type sections."""
    sec_type = sec_elem.get("sec-type", "").lower()
    if sec_type in _SKIP_SECTION_TYPES:
        return

    title_el = sec_elem.find("title")
    section_title = _elem_text(title_el).strip() if title_el is not None else None

    if section_title and _SKIP_TITLE_PATTERNS.match(
        re.sub(r"^[\d.\s]+", "", section_title).strip()
    ):
        return

    # Check for nested sections
    sub_secs = sec_elem.findall("sec")
    if sub_secs:
        # Get any direct paragraph text before sub-sections
        direct_text = _get_direct_paragraphs(sec_elem)
        if direct_text and len(direct_text) // _CHARS_PER_TOKEN >= MIN_CHUNK_TOKENS:
            sections.append((section_title or "Introduction", direct_text))
        for sub in sub_secs:
            _extract_sec_recursive(sub, sections)
    else:
        text = _get_all_text(sec_elem, skip_title=True)
        if text:
            sections.append((section_title or "Untitled Section", text))


def _get_direct_paragraphs(sec_elem) -> str:
    """Get text only from direct <p> children (not nested <sec>)."""
    parts = []
    for child in sec_elem:
        if child.tag == "p":
            parts.append(_elem_text(child))
    return "\n\n".join(p for p in parts if p.strip())


def _get_all_text(elem, skip_title: bool = False) -> str:
    """Get all text content from an element, excluding <title> if skip_title."""
    parts = []
    for child in elem:
        if skip_title and child.tag == "title":
            continue
        if child.tag == "sec":
            continue  # handled recursively
        parts.append(_elem_text(child))
    return "\n\n".join(p for p in parts if p.strip())


def _elem_text(elem) -> str:
    """Recursively extract all text from an XML element."""
    if elem is None:
        return ""
    texts = []
    if elem.text:
        texts.append(elem.text)
    for child in elem:
        texts.append(_elem_text(child))
        if child.tail:
            texts.append(child.tail)
    return " ".join(texts)


# ------------------------------------------------------------------
# Chunking helpers
# ------------------------------------------------------------------

def _sliding_window(
    text: str,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
) -> List[Dict]:
    max_chars = max_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[Dict] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append({
                "index": 0,
                "heading": None,
                "content": current.strip(),
                "token_est": len(current) // _CHARS_PER_TOKEN,
            })
            current = current[-overlap_chars:] + "\n\n" + para if overlap_chars else para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        token_est = len(current) // _CHARS_PER_TOKEN
        if token_est >= MIN_CHUNK_TOKENS:
            chunks.append({
                "index": 0,
                "heading": None,
                "content": current.strip(),
                "token_est": token_est,
            })
    return chunks


def _strip_citations(text: str) -> str:
    for pat in _CITATION_PATTERNS:
        text = pat.sub("", text)
    return re.sub(r"  +", " ", text).strip()


def _clean_ws(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _detect_language(text: str) -> str:
    try:
        return detect(text[:2000])
    except Exception:
        return "en"
