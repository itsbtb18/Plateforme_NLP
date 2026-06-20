from urllib.parse import urlparse

from django.conf import settings


def runtime_urls(request):
    """Expose browser-facing runtime URLs to templates."""

    configured_url = getattr(settings, "FASTAPI_BROWSER_URL", "") or getattr(
        settings, "FASTAPI_URL", ""
    )

    browser_url = "/ai"
    if configured_url:
        parsed = urlparse(configured_url)
        hostname = (parsed.hostname or "").lower()
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            browser_url = configured_url.rstrip("/")
        elif configured_url.startswith("/"):
            browser_url = configured_url.rstrip("/")

    # If the browser reaches Django directly on a non-standard local port
    # (for example localhost:8888 in docker-compose), /ai is not proxied by nginx.
    # In that case, call the published FastAPI host port directly.
    request_host = request.get_host().split(":")[0].lower() if request else ""
    request_port = request.get_port() if request else ""
    if (
        browser_url.startswith("/")
        and request_host in {"localhost", "127.0.0.1", "::1"}
        and request_port not in {"80", "443", ""}
    ):
        browser_url = getattr(
            settings,
            "FASTAPI_LOCAL_BROWSER_URL",
            "http://localhost:8000",
        ).rstrip("/")

    return {
        "FASTAPI_BROWSER_URL": browser_url,
    }