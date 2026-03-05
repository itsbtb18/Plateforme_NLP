"""
PDF download and text-extraction utilities for the scraping module.

Uses PyMuPDF (fitz) to extract text from academic PDFs.
Designed to be failure-safe — never raises on bad/corrupt PDFs.

Limits:
  - Max download size: 20 MB (configurable)
  - Max pages extracted: configurable (default first 3 pages)
  - Max characters returned: configurable (default 12 000)
  - Download timeout: 30 s
"""

import io
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── Defaults ────────────────────────────────────────────────────────
MAX_PDF_BYTES = 20 * 1024 * 1024   # 20 MB
MAX_PAGES = 3                       # first N pages
MAX_CHARS = 12_000                  # truncate extracted text
DOWNLOAD_TIMEOUT = 30               # seconds


def download_pdf(
    url: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = DOWNLOAD_TIMEOUT,
    max_bytes: int = MAX_PDF_BYTES,
) -> Optional[bytes]:
    """
    Download a PDF from *url* and return its raw bytes.

    Returns ``None`` on any failure (network, too large, non-PDF).
    """
    if not url:
        return None

    http = session or requests.Session()
    try:
        # Stream to check Content-Length before downloading fully
        resp = http.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            logger.debug("Skipping non-PDF content-type: %s", content_type)
            resp.close()
            return None

        length = resp.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            logger.info("PDF too large (%s bytes), skipping: %s", length, url)
            resp.close()
            return None

        # Read up to max_bytes + 1 to detect oversized PDFs without Content-Length
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65_536):
            total += len(chunk)
            if total > max_bytes:
                logger.info("PDF exceeded %d bytes during download, aborting: %s", max_bytes, url)
                resp.close()
                return None
            chunks.append(chunk)

        return b"".join(chunks)

    except requests.Timeout:
        logger.warning("PDF download timed out after %ds: %s", timeout, url)
    except requests.RequestException as exc:
        logger.warning("PDF download failed for %s: %s", url, exc)
    return None


def extract_text(
    pdf_bytes: bytes,
    *,
    max_pages: int = MAX_PAGES,
    max_chars: int = MAX_CHARS,
) -> Optional[str]:
    """
    Extract text from the first *max_pages* of a PDF.

    Returns the concatenated text (truncated to *max_chars*), or ``None``
    if extraction fails.
    """
    if not pdf_bytes:
        return None

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — PDF extraction unavailable")
        return None

    try:
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    except Exception as exc:
        logger.warning("Failed to open PDF: %s", exc)
        return None

    try:
        pages_text: list[str] = []
        page_count = min(len(doc), max_pages)

        for i in range(page_count):
            page = doc[i]
            text = page.get_text("text")
            if text:
                pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
        if not full_text.strip():
            return None

        # Truncate to max_chars
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n[… truncated]"

        return full_text

    except Exception as exc:
        logger.warning("PDF text extraction error: %s", exc)
        return None
    finally:
        doc.close()


def download_and_extract(
    url: str,
    *,
    session: Optional[requests.Session] = None,
    max_pages: int = MAX_PAGES,
    max_chars: int = MAX_CHARS,
) -> Optional[str]:
    """
    One-shot: download a PDF and extract text.

    Returns extracted text or ``None`` on any failure.
    """
    pdf_bytes = download_pdf(url, session=session)
    if pdf_bytes is None:
        return None
    return extract_text(pdf_bytes, max_pages=max_pages, max_chars=max_chars)
