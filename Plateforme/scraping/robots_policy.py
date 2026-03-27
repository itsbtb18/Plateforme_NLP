import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from django.core.cache import cache

from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)


def can_fetch(url: str, user_agent: str = "*") -> bool:
    """
    Returns True if robots.txt allows fetching the URL.
    Returns True on any error (fail-open policy for availability).
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        cache_key = f"robots:{parsed.netloc}"

        rp = cache.get(cache_key)
        if rp is None:
            import requests
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                resp = requests.get(robots_url, timeout=SS.ROBOTS_TIMEOUT)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
            except Exception as e:
                logger.debug("robots_download_failed", extra={"url": robots_url, "error": str(e)})
            
            cache.set(cache_key, rp, SS.ROBOTS_CACHE_TTL)

        allowed = rp.can_fetch(user_agent, url)
        if not allowed:
            logger.info(
                "robots_disallowed",
                extra={"url": url, "robots_url": robots_url},
            )
        return allowed
    except Exception as exc:
        logger.debug(
            "robots_check_failed",
            extra={"url": url, "error": str(exc)},
        )
        return True  # fail open
