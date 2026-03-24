import hashlib
import logging
from pathlib import Path
import socket
import ipaddress
import requests
from urllib.parse import urlparse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.conf import settings


class SSRFViolation(Exception):
    """Raised when a URL resolves to an unsafe SSRF target."""

    def __init__(self, offending_ip, message=None):
        self.offending_ip = str(offending_ip)
        super().__init__(message or f"Blocked SSRF target IP: {self.offending_ip}")


logger = logging.getLogger(__name__)

IMAGE_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

PDF_MIME_TYPES = {
    "application/pdf": ".pdf",
}

MAX_DOCUMENT_SIZE_MB = 50
MAX_IMAGE_SIZE_MB = 10

_BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]

_BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),  # loopback
    ipaddress.ip_network("fc00::/7"),  # unique local (private)
    ipaddress.ip_network("fe80::/10"),  # link-local
]


def _host_allowed(hostname, allowed_domains):
    if not allowed_domains:
        return True

    host = (hostname or "").rstrip(".").lower()
    for allowed in allowed_domains:
        domain = (allowed or "").strip().rstrip(".").lower().lstrip(".")
        if not domain:
            continue
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def _resolve_host_ips(hostname):
    addresses = set()
    for info in socket.getaddrinfo(hostname, None):
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = sockaddr[0]
        if ip:
            addresses.add(ip)
    return sorted(addresses)


def _is_blocked_ip(ip_obj):
    # Handle IPv4-mapped IPv6 addresses like ::ffff:10.0.0.1
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        return _is_blocked_ip(ip_obj.ipv4_mapped)

    if isinstance(ip_obj, ipaddress.IPv4Address):
        return any(ip_obj in network for network in _BLOCKED_IPV4_NETWORKS)

    return any(ip_obj in network for network in _BLOCKED_IPV6_NETWORKS)


def validate_url_safety(url, allowed_domains=None):
    """
    Validate URL safety against SSRF targets.

    - Resolves hostname to IP(s)
    - Blocks RFC1918 private ranges
    - Blocks loopback and link-local ranges
    - Blocks IPv6 equivalents
    - Optional allowlist via allowed_domains

    Returns True when safe, raises SSRFViolation when unsafe.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise SSRFViolation("unknown", f"Invalid URL hostname: {url}")

    resolved_ips = _resolve_host_ips(hostname)

    if allowed_domains and not _host_allowed(hostname, allowed_domains):
        offending = resolved_ips[0] if resolved_ips else hostname
        raise SSRFViolation(
            offending,
            f"Host '{hostname}' is not in allowed_domains",
        )

    for ip_str in resolved_ips:
        ip_obj = ipaddress.ip_address(ip_str)
        if _is_blocked_ip(ip_obj):
            raise SSRFViolation(ip_str)

    return True


def _url_hash(url):
    return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()[:8]


def _safe_slug(name):
    value = slugify((name or "").strip())
    return value or "item"


def _build_storage_dir(category, file_type):
    bucket = "images" if file_type == "image" else "pdfs"
    return f"scraping/{category}/{bucket}"


def _find_existing_by_hash(category, file_type, url_hash):
    storage_dir = _build_storage_dir(category, file_type)
    media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
    if not media_root:
        return None

    target_dir = media_root / storage_dir
    if not target_dir.exists() or not target_dir.is_dir():
        return None

    pattern = f"*_{url_hash}.*" if file_type == "image" else f"*_{url_hash}.pdf"
    matches = sorted(target_dir.glob(pattern))
    if not matches:
        return None

    return f"{storage_dir}/{matches[0].name}".replace("\\", "/")


def _allowed_mime_map(file_type):
    return IMAGE_MIME_TYPES if file_type == "image" else PDF_MIME_TYPES


def download_file(
    url,
    category,
    item_name="",
    file_type="document",
    timeout=30,
    allowed_domains=None,
):
    """
    Download a file from URL.
    Returns (ContentFile|None, filename|None, mime_type|None)
    or (None, None, None) on failure.

    If URL hash already exists in target policy path,
    returns (None, existing_filename, mime_or_none) to skip re-download.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None, None, None

    try:
        validate_url_safety(url, allowed_domains=allowed_domains)
    except SSRFViolation:
        raise
    except Exception as exc:
        logger.warning(
            "File download blocked due to URL safety validation error: %s", exc
        )
        return None, None, None

    url_hash = _url_hash(url)
    existing_file = _find_existing_by_hash(category, file_type, url_hash)
    if existing_file:
        logger.info("File download skipped (existing URL hash): %s", url)
        return None, existing_file, None

    max_mb = MAX_IMAGE_SIZE_MB if file_type == "image" else MAX_DOCUMENT_SIZE_MB
    max_bytes = max_mb * 1024 * 1024
    allowed_mimes = _allowed_mime_map(file_type)

    try:
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
            headers={"User-Agent": ("Mozilla/5.0 NLPPlatformBot/1.0")},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()

        if content_type not in allowed_mimes:
            logger.warning(
                "Rejected file MIME type '%s' for url=%s category=%s",
                content_type,
                url,
                category,
            )
            return None, None, None

        extension = allowed_mimes[content_type]

        content = b""
        size = 0
        for chunk in response.iter_content(8192):
            if not chunk:
                continue
            content += chunk
            size += len(chunk)
            if size > max_bytes:
                logger.warning(
                    "Rejected file larger than policy max (%d MB) for url=%s",
                    max_mb,
                    url,
                )
                return None, None, None

        base_name = _safe_slug(item_name)
        storage_dir = _build_storage_dir(category, file_type)
        filename = f"{storage_dir}/{base_name}_{url_hash}{extension}".replace("\\", "/")
        return ContentFile(content), filename, content_type

    except Exception:
        logger.warning("File download failed for url=%s", url, exc_info=True)
        return None, None, None


def try_download_document(urls, category, item_name="", allowed_domains=None):
    """Try multiple URLs, return first successful download."""
    for url in urls or []:
        if not url:
            continue
        content, filename, mime = download_file(
            url,
            category,
            item_name=item_name,
            file_type="document",
            allowed_domains=allowed_domains,
        )
        if filename:
            return content, filename
    return None, None


def try_download_image(urls, category, item_name="", allowed_domains=None):
    """Try multiple image URLs, return first success."""
    for url in urls or []:
        if not url:
            continue
        content, filename, mime = download_file(
            url,
            category,
            item_name=item_name,
            file_type="image",
            allowed_domains=allowed_domains,
        )
        if filename:
            return content, filename
    return None, None


def attach_file_to_model(instance, field_name, content_file, filename):
    """
    Attach a downloaded ContentFile to a model FileField.
    Returns True on success, False on failure.
    """
    if not filename:
        return False

    try:
        field = getattr(instance, field_name, None)
        if field is None:
            return False

        # Reuse already-existing stored file (hash-skip case).
        if content_file is None:
            field.name = filename
            instance.save(update_fields=[field_name])
            return True

        # Store directly in policy path when filename includes directories.
        if "/" in filename or "\\" in filename:
            saved_name = default_storage.save(filename, content_file)
            field.name = saved_name
            instance.save(update_fields=[field_name])
            return True

        # Backward-compatible fallback for plain filenames.
        field.save(filename, content_file, save=True)
        return True
    except Exception:
        logger.warning(
            "Failed to attach downloaded file to model field '%s'. Clearing field.",
            field_name,
            exc_info=True,
        )
        try:
            setattr(instance, field_name, None)
            instance.save(update_fields=[field_name])
        except Exception:
            pass
        return False
