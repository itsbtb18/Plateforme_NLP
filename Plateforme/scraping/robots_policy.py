import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from django.core.cache import cache

logger = logging.getLogger(__name__)
ROBOTS_CACHE_TTL = 3600  # 1 hour


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
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            cache.set(cache_key, rp, ROBOTS_CACHE_TTL)

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
