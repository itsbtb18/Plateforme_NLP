"""
PDF download and text-extraction utilities for the scraping module.

Uses PyMuPDF (fitz) to extract text from academic PDFs.
Designed to be failure-safe — never raises on bad/corrupt PDFs.

Limits:
    - Max download size: 50 MB (configurable)
  - Max pages extracted: configurable (default first 3 pages)
  - Max characters returned: configurable (default 12 000)
  - Download timeout: 30 s
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── Defaults ────────────────────────────────────────────────────────
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PAGES = 3  # first N pages
MAX_CHARS = 12_000  # truncate extracted text
DOWNLOAD_TIMEOUT = 30  # seconds


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

    try:
        from scraping.file_downloader import validate_url_safety

        validate_url_safety(url)
    except Exception as exc:
        logger.warning("PDF URL rejected by SSRF safety validation: %s", exc)
        return None

    http = session or requests.Session()
    try:
        # Stream to check Content-Length before downloading fully
        resp = http.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()

        content_type = (
            resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        )
        if content_type != "application/pdf":
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
                logger.info(
                    "PDF exceeded %d bytes during download, aborting: %s",
                    max_bytes,
                    url,
                )
                resp.close()
                return None
            chunks.append(chunk)

        return b"".join(chunks)

    except requests.Timeout:
        logger.warning("PDF download timed out after %ds: %s", timeout, url)
    except requests.RequestException as exc:
        logger.warning("PDF download failed for %s: %s", url, exc)
    return None


class ExtractionResult(str):
    """
    String subclass that also carries structured extraction data.

    Old callers that treat the return value as a plain string (truthiness
    check, ``len()``, slicing …) keep working.  New callers can access the
    dict-style payload::

        result = extract_text(pdf_bytes)
        print(result)                    # the full text (str)
        print(result['sections'])        # section dict
        print(result['page_count'])      # int
    """

    def __new__(cls, result_dict: dict):
        text = result_dict.get("full_text", "")
        instance = super().__new__(cls, text)
        instance._data = result_dict
        return instance

    # dict-style access -------------------------------------------------
    def __getitem__(self, key):  # result['sections']
        if isinstance(key, str):
            return self._data[key]
        return super().__getitem__(key)  # str slicing still works

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


def extract_text(pdf_bytes, max_chars=12000):
    """
    Extract text from PDF with section detection.
    Returns dict with keys:
    - full_text: complete extracted text (string)
    - sections: dict with abstract, introduction,
      methodology, results, conclusion, references
    - page_count: number of pages
    - error: error message if any
    """
    import fitz
    import re

    sections = {
        "abstract": "",
        "introduction": "",
        "methodology": "",
        "results": "",
        "conclusion": "",
        "references": "",
    }

    SECTION_PATTERNS = {
        "abstract": [
            r"\babstract\b",
            r"\bملخص\b",
            r"\brésumé\b",
            r"\babrégé\b",
        ],
        "introduction": [
            r"\bintroduction\b",
            r"\b1[\.\s]+introduction\b",
            r"\bمقدمة\b",
        ],
        "methodology": [
            r"\bmethodology\b",
            r"\bmethod\b",
            r"\bapproach\b",
            r"\bproposed method\b",
            r"\bمنهجية\b",
            r"\bنهج\b",
            r"\bméthode\b",
            r"\bméthodologie\b",
        ],
        "results": [
            r"\bresults\b",
            r"\bexperiments\b",
            r"\bevaluation\b",
            r"\bنتائج\b",
            r"\bتجارب\b",
            r"\brésultats\b",
            r"\bexpériences\b",
        ],
        "conclusion": [
            r"\bconclusion\b",
            r"\bconclusions\b",
            r"\bsummary\b",
            r"\bخاتمة\b",
            r"\باستنتاج\b",
        ],
        "references": [
            r"\breferences\b",
            r"\bbibliography\b",
            r"\bالمراجع\b",
            r"\bالمصادر\b",
            r"\bréférences\b",
            r"\bbibliographie\b",
        ],
    }

    compiled = {}
    for section_name, patterns in SECTION_PATTERNS.items():
        combined = "|".join(f"({p})" for p in patterns)
        compiled[section_name] = re.compile(combined, re.IGNORECASE | re.UNICODE)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        full_text = ""
        current_section = None

        for page in doc:
            if len(full_text) >= max_chars:
                break

            page_text = page.get_text("text")
            full_text += page_text + "\n"

            for line in page_text.split("\n"):
                line_clean = line.strip()
                if len(line_clean) < 2:
                    continue
                for section_name, pattern in compiled.items():
                    if pattern.search(line_clean):
                        current_section = section_name
                        break

                if current_section and current_section != "references":
                    sections[current_section] += line + "\n"

        doc.close()

        # Truncate
        full_text = full_text[:max_chars]
        for key in sections:
            sections[key] = sections[key][:2000].strip()

        return {
            "full_text": full_text,
            "sections": sections,
            "page_count": page_count,
            "error": None,
        }

    except Exception as e:
        return {
            "full_text": "",
            "sections": sections,
            "page_count": 0,
            "error": str(e),
        }


def download_and_extract(
    url: str,
    *,
    session: Optional[requests.Session] = None,
    max_chars: int = MAX_CHARS,
) -> Optional[ExtractionResult]:
    """
    One-shot: download a PDF and extract text with section detection.

    Returns an :class:`ExtractionResult` (``str`` subclass with dict-style
    access to ``full_text``, ``sections``, ``page_count``) or ``None`` on
    download failure.  Old callers that treat the return value as a plain
    string keep working unchanged.
    """
    pdf_bytes = download_pdf(url, session=session)
    if pdf_bytes is None:
        return None
    result = extract_text(pdf_bytes, max_chars=max_chars)
    # Return ExtractionResult even if full_text is empty, so callers can read 'error'
    return ExtractionResult(result)
