import hashlib
import ipaddress
import json
import logging
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify


class DownloadResult:
    """Typed outcome codes for every download_file() return path."""

    SUCCESS = "success"
    SKIP_EXISTS = "skip_exists"
    FAIL_MIME = "fail_mime"
    FAIL_SIZE = "fail_size"
    FAIL_SSRF = "fail_ssrf"
    FAIL_HEAD = "fail_head"
    FAIL_NETWORK = "fail_network"
    FAIL_WRITE = "fail_write"


class SSRFViolationError(Exception):
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

MAX_DOCUMENT_SIZE_MB = int(os.environ.get("SCRAPING_MAX_DOCUMENT_MB", 50))
MAX_IMAGE_SIZE_MB = int(os.environ.get("SCRAPING_MAX_IMAGE_MB", 10))

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


class _DownloadTooLargeError(Exception):
    """Raised when streamed GET response exceeds policy size limit."""


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Disable automatic redirect following for GET downloads."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


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

    Returns True when safe, raises SSRFViolationError when unsafe.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise SSRFViolationError("unknown", f"Invalid URL hostname: {url}")

    resolved_ips = _resolve_host_ips(hostname)

    if allowed_domains and not _host_allowed(hostname, allowed_domains):
        offending = resolved_ips[0] if resolved_ips else hostname
        raise SSRFViolationError(
            offending,
            f"Host '{hostname}' is not in allowed_domains",
        )

    for ip_str in resolved_ips:
        ip_obj = ipaddress.ip_address(ip_str)
        if _is_blocked_ip(ip_obj):
            raise SSRFViolationError(ip_str)

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


def _find_existing_by_url(url, category, file_type):
    """Scan sidecar .meta.json files to find an existing download by URL."""
    storage_dir = _build_storage_dir(category, file_type)
    media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
    if not media_root:
        return None

    target_dir = media_root / storage_dir
    if not target_dir.exists() or not target_dir.is_dir():
        return None

    for meta_file in target_dir.glob("*.meta.json"):
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("original_url") == url:
                asset_path = str(meta_file).replace(".meta.json", "")
                if Path(asset_path).exists():
                    rel = f"{storage_dir}/{Path(asset_path).name}".replace("\\", "/")
                    return rel
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "download_sidecar_lookup_skipped_due_to_error",
                extra={"error": str(exc), "context": str(meta_file)},
                exc_info=False,
            )
            continue
    return None


def _allowed_mime_map(file_type):
    return IMAGE_MIME_TYPES if file_type == "image" else PDF_MIME_TYPES


def _get_headers():
    return {"User-Agent": "Mozilla/5.0 NLPPlatformBot/1.0"}


def _normalize_content_type(raw_content_type):
    return (raw_content_type or "").split(";")[0].strip().lower()


def _parse_content_length(raw_content_length):
    try:
        return int(raw_content_length or 0)
    except (TypeError, ValueError):
        return 0


def _head_preflight(url, timeout, headers):
    req = urllib_request.Request(url, headers=headers, method="HEAD")
    with urllib_request.urlopen(req, timeout=timeout) as response:
        content_type = _normalize_content_type(response.headers.get("Content-Type"))
        content_length = _parse_content_length(response.headers.get("Content-Length"))
        return content_type, content_length


def _download_via_get(url, timeout, headers, max_bytes):
    req = urllib_request.Request(url, headers=headers, method="GET")
    opener = urllib_request.build_opener(_NoRedirectHandler())
    with opener.open(req, timeout=timeout) as response:
        content_type = _normalize_content_type(response.headers.get("Content-Type"))

        chunks = []
        size = 0
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                raise _DownloadTooLargeError()

        return content_type, b"".join(chunks), size


def download_file(
    url,
    category,
    item_name="",
    file_type="document",
    timeout=30,
    allowed_domains=None,
):
    """
    Download a file from URL with HEAD preflight.

    Returns (ContentFile|None, filename|None, DownloadResult code).
    """
    if not url or not url.startswith(("http://", "https://")):
        return None, None, DownloadResult.FAIL_NETWORK

    try:
        validate_url_safety(url, allowed_domains=allowed_domains)
    except SSRFViolationError:
        raise
    except Exception as exc:
        logger.warning(
            "File download blocked due to URL safety validation error: %s", exc
        )
        return None, None, DownloadResult.FAIL_SSRF

    # ── Sidecar check — already downloaded this exact URL? ──────────
    existing_by_url = _find_existing_by_url(url, category, file_type)
    if existing_by_url:
        logger.info("File download skipped (sidecar URL match): %s", url)
        return None, existing_by_url, DownloadResult.SKIP_EXISTS

    # ── Hash-based dedup (legacy) ───────────────────────────────────
    url_hash = _url_hash(url)
    existing_file = _find_existing_by_hash(category, file_type, url_hash)
    if existing_file:
        logger.info("File download skipped (existing URL hash): %s", url)
        return None, existing_file, DownloadResult.SKIP_EXISTS

    max_mb = MAX_IMAGE_SIZE_MB if file_type == "image" else MAX_DOCUMENT_SIZE_MB
    max_bytes = max_mb * 1024 * 1024
    allowed_mimes = _allowed_mime_map(file_type)
    request_headers = _get_headers()

    # ── HEAD preflight ──────────────────────────────────────────────
    try:
        content_type, content_length = _head_preflight(
            url,
            timeout=10,
            headers=request_headers,
        )
    except Exception as e:
        logger.warning("head_request_failed", extra={"url": url, "error": str(e)})
        return None, None, DownloadResult.FAIL_HEAD

    if content_type not in allowed_mimes:
        logger.warning(
            "mime_rejected_via_head", extra={"url": url, "content_type": content_type}
        )
        return None, None, DownloadResult.FAIL_MIME

    if content_length > max_bytes:
        logger.warning(
            "size_rejected_via_head",
            extra={"url": url, "content_length": content_length},
        )
        return None, None, DownloadResult.FAIL_SIZE

    # ── GET (only after HEAD passes) ────────────────────────────────
    try:
        get_ct, content, size = _download_via_get(
            url,
            timeout=timeout,
            headers=request_headers,
            max_bytes=max_bytes,
        )

        if get_ct not in allowed_mimes:
            logger.warning(
                "Rejected file MIME type '%s' for url=%s category=%s",
                get_ct,
                url,
                category,
            )
            return None, None, DownloadResult.FAIL_MIME

        extension = allowed_mimes[get_ct]

        base_name = _safe_slug(item_name)
        storage_dir = _build_storage_dir(category, file_type)
        filename = f"{storage_dir}/{base_name}_{url_hash}{extension}".replace("\\", "/")

        # ── Compute SHA-256 ─────────────────────────────────────────
        sha256_hash = hashlib.sha256(content).hexdigest()

        # ── Write sidecar .meta.json ────────────────────────────────
        try:
            media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
            if media_root:
                local_path = media_root / filename
                local_path.parent.mkdir(parents=True, exist_ok=True)

                meta = {
                    "original_url": url,
                    "downloaded_at": datetime.now(UTC).isoformat(),
                    "content_type": get_ct,
                    "file_size_bytes": size,
                    "sha256": sha256_hash,
                    "category": category,
                    "item_name": item_name,
                }
                meta_path = str(local_path) + ".meta.json"
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
        except Exception as meta_exc:
            logger.warning(
                "Failed to write sidecar .meta.json for %s: %s",
                url,
                meta_exc,
            )

        return ContentFile(content), filename, DownloadResult.SUCCESS
    except _DownloadTooLargeError:
        logger.warning(
            "Rejected file larger than policy max (%d MB) for url=%s",
            max_mb,
            url,
        )
        return None, None, DownloadResult.FAIL_SIZE
    except urllib_error.HTTPError as exc:
        logger.warning(
            "File download HTTP error for url=%s code=%s",
            url,
            getattr(exc, "code", "unknown"),
            exc_info=False,
        )
        return None, None, DownloadResult.FAIL_NETWORK
    except urllib_error.URLError:
        logger.warning("File download failed for url=%s", url, exc_info=True)
        return None, None, DownloadResult.FAIL_NETWORK
    except Exception:
        logger.warning("File download failed for url=%s", url, exc_info=True)
        return None, None, DownloadResult.FAIL_NETWORK


def try_download_document(urls, category, item_name="", allowed_domains=None):
    """Try multiple URLs, return first successful download."""
    for url in urls or []:
        if not url:
            continue
        content, filename, result_code = download_file(
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
        content, filename, result_code = download_file(
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
        except (AttributeError, ValueError, TypeError, OSError) as exc:
            logger.warning(
                "model_field_clear_failed_after_attach_error",
                extra={
                    "error": str(exc),
                    "context": f"{instance.__class__.__name__}.{field_name}",
                },
                exc_info=False,
            )
        return False
