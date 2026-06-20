"""
PDF ingestion core using Docling — v2 (CPU-optimised).

Key improvements over v1:
  - Filters out References, Bibliography, Appendix, Acknowledgments
  - 800–1200 token target window (reduced chunk count)
  - Drops tiny chunks (< 50 tokens) and merges them into neighbours
  - Strips inline citation markers
  - Single-document, memory-safe processing
  - No OCR, no table structure (CPU-friendly)
"""

import re
import logging
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from langdetect import detect

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4

# Headings that signal non-content sections to skip
_SKIP_HEADINGS = re.compile(
    r"^\s*("
    r"references|bibliography|bibliographie|"
    r"appendix|appendices|annexe|annexes|"
    r"acknowledgments?|acknowledgements?|remerciements|"
    r"conflict.{0,5}of.{0,5}interest|"
    r"funding|author.{0,5}contributions?|"
    r"data.{0,5}availability|supplementary.{0,5}materials?"
    r")\s*$",
    re.IGNORECASE,
)

# Inline citation patterns to strip
_CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[,;\s]+\d+)*\]"),
    re.compile(
        r"\(\w+(?:\s+et\s+al\.?)?,?\s*\d{4}"
        r"(?:[;,]\s*\w+(?:\s+et\s+al\.?)?,?\s*\d{4})*\)"
    ),
]

MIN_CHUNK_TOKENS = 50

# Files larger than this use PyPDF2 (lightweight) instead of Docling
LARGE_FILE_THRESHOLD_MB = 5.0


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def load_and_chunk_pdf(
    pdf_path: str | Path,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
) -> Dict:
    """Parse a PDF, filter junk sections, clean text, chunk.

    Uses PyPDF2 (lightweight) for large files to avoid OOM,
    Docling (structured) for smaller files.

    Returns::

        {
            "title": str,
            "language": str,
            "chunks": [
                {
                    "index": int,
                    "heading": str | None,
                    "content": str,
                    "token_est": int,
                },
            ],
        }
    """
    pdf_path = Path(pdf_path)
    size_mb = pdf_path.stat().st_size / 1e6
    logger.info("Loading PDF: %s (%.1f MB)", pdf_path.name, size_mb)

    if size_mb > LARGE_FILE_THRESHOLD_MB:
        logger.info("Large file — using PyPDF2 (lightweight) instead of Docling")
        return _load_with_pypdf2(pdf_path, max_tokens, overlap_tokens)

    return _load_with_docling(pdf_path, max_tokens, overlap_tokens)


def _load_with_docling(
    pdf_path: Path,
    max_tokens: int,
    overlap_tokens: int,
) -> Dict:
    """Full Docling pipeline for smaller PDFs."""
    # Lazy imports so module loads fast without Docling
    from docling.chunking import HierarchicalChunker
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_opts = PdfPipelineOptions()
    pipeline_opts.do_ocr = False
    pipeline_opts.do_table_structure = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
        }
    )
    result = converter.convert(str(pdf_path))
    doc = result.document

    title = _extract_title(doc, pdf_path)

    # Chunk with section filtering
    chunks = _chunk_with_docling_filtered(doc, max_tokens)

    if not chunks:
        logger.info("HierarchicalChunker yielded 0 usable chunks — fallback to sliding-window")
        md_text = doc.export_to_markdown()
        md_text = _filter_markdown_sections(md_text)
        md_text = _clean_text(md_text)
        chunks = _sliding_window_chunks(md_text, max_tokens, overlap_tokens)

    # Merge tiny chunks
    chunks = _merge_tiny_chunks(chunks, min_tokens=MIN_CHUNK_TOKENS)

    # Detect language
    sample = " ".join(c["content"][:500] for c in chunks[:3])
    language = _detect_language(sample)

    logger.info("PDF done: title='%s', chunks=%d, lang=%s", title, len(chunks), language)
    return {"title": title, "language": language, "chunks": chunks}


def _load_with_pypdf2(
    pdf_path: Path,
    max_tokens: int,
    overlap_tokens: int,
) -> Dict:
    """Lightweight PDF text extraction using PyPDF2 — no layout model.

    Uses ~10x less memory than Docling. Suitable for large textbooks.
    """
    import PyPDF2

    title = pdf_path.stem
    all_text = []

    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        logger.info("PyPDF2: %d pages", len(reader.pages))
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.replace("\x00", "").strip()
            if text:
                all_text.append(text)

    full_text = "\n\n".join(all_text)
    full_text = _filter_markdown_sections(full_text)
    full_text = _clean_text(full_text)
    full_text = _strip_citations(full_text)

    chunks = _sliding_window_chunks(full_text, max_tokens, overlap_tokens)
    chunks = _merge_tiny_chunks(chunks, min_tokens=MIN_CHUNK_TOKENS)

    sample = " ".join(c["content"][:500] for c in chunks[:3])
    language = _detect_language(sample)

    logger.info("PDF done (PyPDF2): title='%s', chunks=%d, lang=%s", title, len(chunks), language)
    return {"title": title, "language": language, "chunks": chunks}


def extract_keywords(text: str, max_kw: int = 15) -> List[str]:
    """Leverage Phase-10 entity extractor for keyword extraction."""
    from app.services.documents.entities import extract_entities
    return extract_entities(text[:8000])[:max_kw]


# ------------------------------------------------------------------
# Section filtering
# ------------------------------------------------------------------

def _should_skip_heading(heading: Optional[str]) -> bool:
    """Return True if this heading marks a non-content section."""
    if not heading:
        return False
    clean = re.sub(r"^[\d.\s]+", "", heading).strip()
    return bool(_SKIP_HEADINGS.match(clean))


def _filter_markdown_sections(text: str) -> str:
    """Remove everything after a References/Bibliography heading in markdown."""
    lines = text.split("\n")
    filtered = []
    for line in lines:
        heading_match = re.match(r"^#+\s+(.*)", line)
        if heading_match and _should_skip_heading(heading_match.group(1)):
            break
        filtered.append(line)
    return "\n".join(filtered)


# ------------------------------------------------------------------
# Docling chunker with filtering
# ------------------------------------------------------------------

def _chunk_with_docling_filtered(doc, max_tokens: int) -> List[Dict]:
    """Section-aware chunking via Docling, skipping reference sections."""
    from docling.chunking import HierarchicalChunker

    try:
        chunker = HierarchicalChunker(max_tokens=max_tokens)
        raw = list(chunker.chunk(doc))
    except Exception as exc:
        logger.warning("HierarchicalChunker error: %s", exc)
        return []

    out: List[Dict] = []
    seen_skip = False

    for chunk in raw:
        text = chunk.text if hasattr(chunk, "text") else str(chunk)

        heading = None
        meta = getattr(chunk, "meta", None)
        if meta:
            headings = getattr(meta, "headings", None)
            if isinstance(headings, list) and headings:
                heading = headings[-1]

        if heading and _should_skip_heading(heading):
            seen_skip = True
            logger.debug("Skipping section: %s", heading)
            continue
        if seen_skip:
            continue

        text = _clean_text(text)
        text = _strip_citations(text)
        token_est = len(text) // _CHARS_PER_TOKEN

        if token_est < MIN_CHUNK_TOKENS:
            continue

        out.append({
            "index": len(out),
            "heading": heading,
            "content": text,
            "token_est": token_est,
        })

    return out


# ------------------------------------------------------------------
# Sliding window fallback
# ------------------------------------------------------------------

def _sliding_window_chunks(
    text: str,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
) -> List[Dict]:
    """Paragraph-boundary sliding window (fallback chunker)."""
    max_chars = max_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[Dict] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append({
                "index": len(chunks),
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
                "index": len(chunks),
                "heading": None,
                "content": current.strip(),
                "token_est": token_est,
            })

    return chunks


# ------------------------------------------------------------------
# Post-processing helpers
# ------------------------------------------------------------------

def _merge_tiny_chunks(chunks: List[Dict], min_tokens: int = 50) -> List[Dict]:
    """Merge chunks smaller than min_tokens with their predecessor."""
    if not chunks:
        return []
    merged: List[Dict] = [chunks[0]]
    for chunk in chunks[1:]:
        if chunk["token_est"] < min_tokens and merged:
            prev = merged[-1]
            prev["content"] = prev["content"] + "\n\n" + chunk["content"]
            prev["token_est"] = len(prev["content"]) // _CHARS_PER_TOKEN
        else:
            chunk["index"] = len(merged)
            merged.append(chunk)
    return merged


def _strip_citations(text: str) -> str:
    """Remove inline citation markers like [1,2] or (Author, 2021)."""
    for pat in _CITATION_PATTERNS:
        text = pat.sub("", text)
    return re.sub(r"  +", " ", text).strip()


def _clean_text(text: str) -> str:
    """Remove non-informative artefacts and normalise whitespace."""
    text = text.replace("\x00", "")
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    lines = text.split("\n")
    counts = Counter(ln.strip() for ln in lines if ln.strip())
    repeated = {ln for ln, n in counts.items() if n > 3 and len(ln) < 80}
    if repeated:
        lines = [ln for ln in lines if ln.strip() not in repeated]
        text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_title(doc, pdf_path: Path) -> str:
    """Best-effort title: Docling metadata → filename."""
    if hasattr(doc, "name") and doc.name:
        return str(doc.name).strip()
    return pdf_path.stem


def _detect_language(text: str) -> str:
    try:
        return detect(text[:2000])
    except Exception:
        return "en"
