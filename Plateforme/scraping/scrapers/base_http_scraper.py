"""HTTP scraper base class with render fallback support."""

import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django_redis import get_redis_connection
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scraping.constants import REDIS_CACHE_ALIAS
from scraping.metrics import (
    scraping_circuit_breaker_trips_total,
    scraping_network_failures_total,
    scraping_render_method_total,
    scraping_wayback_fallback_total,
)
from scraping.scrapers.base import BaseScraper
from scraping.scrapers.circuit_breaker import RedisCircuitBreaker
from scraping.scrapers.wayback_fallback import WaybackMachineFallback
from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)

TIMEOUT_SETTINGS = (
    SS.CONNECT_TIMEOUT,
    SS.READ_TIMEOUT,
)  # (connect_timeout, read_timeout)


class BaseHTTPScraper(BaseScraper):
    """Base scraper that supports tracking render method and fallback hooks."""

    PLAYWRIGHT_THRESHOLD = SS.PLAYWRIGHT_CONTENT_THRESHOLD

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=0,
                connect=0,
                read=0,
                redirect=3,
                status_forcelist=[],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = dict(self.session.headers)
        self._redis_client = get_redis_connection(REDIS_CACHE_ALIAS)
        self.base_url = getattr(self, "base_url", "")
        self._network_failures: dict[str, str] = {}

        initial_domain = urlparse(self.base_url).netloc or "unknown"
        self.circuit_breaker = RedisCircuitBreaker(
            redis_client=self._redis_client,
            domain=initial_domain,
        )

    def _ensure_domain_breaker(self, domain: str) -> None:
        target_domain = domain or "unknown"
        if getattr(self.circuit_breaker, "domain", "") != target_domain:
            self.circuit_breaker = RedisCircuitBreaker(
                redis_client=self._redis_client,
                domain=target_domain,
            )

    def should_use_playwright(self, html: str) -> bool:
        """Return True when parsed text content is too small to trust static HTML."""
        soup = BeautifulSoup(html or "", "html.parser")
        text_len = len(soup.get_text(strip=True))
        return text_len < self.PLAYWRIGHT_THRESHOLD

    def fetch_with_fallback(self, url: str) -> tuple[str, str]:
        """Default HTML fetch helper used by subclasses."""
        response = self.fetch(url)
        if response is None:
            return "", "network_failure"
        scraping_render_method_total.labels(method="beautifulsoup").inc()
        return response.text, "beautifulsoup"

    def fetch(self, url: str, **kwargs) -> requests.Response | None:
        domain = urlparse(url).netloc or "unknown"
        source_name = kwargs.pop("source_name", "")
        self._ensure_domain_breaker(domain)
        source_context = self._resolve_source_context(source_name or domain, url)
        previous_source = getattr(self, "_current_source", None)
        self._current_source = source_context

        try:
            # Circuit breaker check BEFORE any HTTP call
            if self.circuit_breaker.is_open():
                logger.warning("[%s] circuit_open - skipping %s", self.category, url)
                self._update_metrics("circuit_open", domain)
                self._network_failures[domain] = "circuit_open"
                return None

            verify_ssl = bool(getattr(source_context, "verify_ssl", True))
            proxy_url = self._resolve_proxy_for_source(source_context)
            headers = dict(self.headers)
            headers["User-Agent"] = self._rotate_user_agent()
            self.session.headers["User-Agent"] = headers["User-Agent"]

            request_kwargs = dict(kwargs)
            if "verify" not in request_kwargs:
                request_kwargs["verify"] = verify_ssl
            if "proxies" not in request_kwargs and proxy_url:
                request_kwargs["proxies"] = {
                    "http": proxy_url,
                    "https": proxy_url,
                }

            response = self.session.get(
                url,
                timeout=TIMEOUT_SETTINGS,
                headers=headers,
                **request_kwargs,
            )
            self.circuit_breaker.record_success()
            self._network_failures.pop(domain, None)
            if source_name:
                self._network_failures.pop(f"{domain}|{source_name}", None)
            return response

        except requests.exceptions.ConnectTimeout:
            fallback_response = self._handle_network_failure(
                url,
                domain,
                "connect_timeout",
                source_name,
            )
            if fallback_response is not None:
                return fallback_response
        except requests.exceptions.ReadTimeout:
            fallback_response = self._handle_network_failure(
                url,
                domain,
                "read_timeout",
                source_name,
            )
            if fallback_response is not None:
                return fallback_response
        except requests.exceptions.ConnectionError as exc:
            error_str = str(exc)
            if (
                "NameResolutionError" in error_str
                or "Errno -2" in error_str
                or "Errno -3" in error_str
            ):
                fallback_response = self._handle_network_failure(
                    url,
                    domain,
                    "dns_failure",
                    source_name,
                )
                if fallback_response is not None:
                    return fallback_response
            elif "Errno 101" in error_str or "Network is unreachable" in error_str:
                fallback_response = self._handle_network_failure(
                    url,
                    domain,
                    "network_unreachable",
                    source_name,
                )
                if fallback_response is not None:
                    return fallback_response
            else:
                fallback_response = self._handle_network_failure(
                    url,
                    domain,
                    "connection_error",
                    source_name,
                )
                if fallback_response is not None:
                    return fallback_response
        except requests.exceptions.SSLError:
            fallback_response = self._handle_network_failure(
                url,
                domain,
                "ssl_error",
                source_name,
            )
            if fallback_response is not None:
                return fallback_response
        except Exception as exc:
            fallback_response = self._handle_network_failure(
                url,
                domain,
                f"unexpected:{type(exc).__name__}",
                source_name,
            )
            if fallback_response is not None:
                return fallback_response
        finally:
            self._current_source = previous_source

        return None

    def _update_metrics(self, error_type: str, domain: str) -> None:
        if error_type == "circuit_open":
            scraping_circuit_breaker_trips_total.labels(domain=domain).inc()
            return
        scraping_network_failures_total.labels(
            error_type=error_type,
            domain=domain,
        ).inc()

    def _handle_network_failure(
        self,
        url,
        domain,
        error_type,
        source_name: str = "",
    ):
        was_open = self.circuit_breaker.is_open()
        self.circuit_breaker.record_failure(error_type)
        is_open_now = self.circuit_breaker.is_open()
        if not was_open and is_open_now:
            scraping_circuit_breaker_trips_total.labels(domain=domain).inc()

        logger.warning(
            "[%s] %s - %s unreachable, skipping. (url=%s)",
            self.category,
            error_type,
            domain,
            url,
        )

        # DNS and transport-level failures can still have usable archived copies.
        if error_type in ("dns_failure", "network_unreachable", "connect_timeout"):
            wayback = WaybackMachineFallback()
            response = wayback.get_latest_snapshot(
                url, max_age_days=SS.WAYBACK_MAX_AGE_DAYS
            )
            if response is not None:
                logger.info(
                    "[%s] wayback_success - Using archived version of %s",
                    self.category,
                    url,
                )
                scraping_wayback_fallback_total.labels(
                    domain=domain,
                    result="success",
                ).inc()
                return response

            logger.info(
                "[%s] wayback_unavailable - No archive for %s",
                self.category,
                url,
            )
            scraping_wayback_fallback_total.labels(
                domain=domain,
                result="unavailable",
            ).inc()

        self._update_metrics(error_type, domain)
        self._network_failures[domain] = error_type
        if source_name:
            self._network_failures[f"{domain}|{source_name}"] = error_type
        # DO NOT raise - just return None silently
        return None
