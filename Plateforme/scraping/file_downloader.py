import os
import uuid
import requests
from django.core.files.base import ContentFile

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

MAX_DOCUMENT_SIZE_MB = 15
MAX_IMAGE_SIZE_MB = 5


def download_file(url, category, file_type="document", timeout=30):
    """
    Download a file from URL.
    Returns (ContentFile, filename, mime_type)
    or (None, None, None) on failure.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None, None, None

    max_mb = MAX_IMAGE_SIZE_MB if file_type == "image" else MAX_DOCUMENT_SIZE_MB
    max_bytes = max_mb * 1024 * 1024

    try:
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={"User-Agent": ("Mozilla/5.0 NLPPlatformBot/1.0")},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()

        if content_type not in ALLOWED_MIME_TYPES:
            return None, None, None

        extension = ALLOWED_MIME_TYPES[content_type]

        content = b""
        size = 0
        for chunk in response.iter_content(8192):
            content += chunk
            size += len(chunk)
            if size > max_bytes:
                return None, None, None

        filename = f"scraped_{category}_{uuid.uuid4().hex[:8]}{extension}"
        return ContentFile(content), filename, content_type

    except Exception:
        return None, None, None


def try_download_document(urls, category):
    """Try multiple URLs, return first successful download."""
    for url in urls or []:
        if not url:
            continue
        content, filename, mime = download_file(url, category, "document")
        if content:
            return content, filename
    return None, None


def try_download_image(urls, category):
    """Try multiple image URLs, return first success."""
    for url in urls or []:
        if not url:
            continue
        content, filename, mime = download_file(url, category, "image")
        if content:
            return content, filename
    return None, None


def attach_file_to_model(instance, field_name, content_file, filename):
    """
    Attach a downloaded ContentFile to a model FileField.
    Returns True on success, False on failure.
    """
    if not content_file or not filename:
        return False
    try:
        field = getattr(instance, field_name, None)
        if field is None:
            return False
        field.save(filename, content_file, save=True)
        return True
    except Exception:
        return False
