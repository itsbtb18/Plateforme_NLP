import logging
import socket
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)


class NetworkValidator:
    """Validate network health and scraping viability for a source URL."""

    CONNECT_TIMEOUT = 3.0
    READ_TIMEOUT = 5.0

    def __init__(self, url: str | None = None, user_agent: str = "*"):
        self.url = url
        self.user_agent = user_agent
        self.session = requests.Session()

    def run(self) -> dict:
        if not self.url:
            raise ValueError("URL is required")
        return self.validate(self.url)

    def validate(self, url: str) -> dict:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)

        domain = parsed.hostname or ""
        target_path = parsed.path or "/"
        canonical_url = f"{parsed.scheme}://{parsed.netloc}{target_path}"

        dns_status = self._test_dns_resolution(domain)
        tcp_status = self._test_tcp_connectivity(domain, parsed.scheme)
        http_status = self._test_http_response(canonical_url)
        robots_status = self._test_robots_compliance(
            parsed.scheme, parsed.netloc, target_path
        )
        rate_limit_status = self._test_rate_limit_detection(canonical_url)

        overall, blocking_reason = self._compute_overall(
            dns_status=dns_status,
            tcp_status=tcp_status,
            http_status=http_status,
            robots_status=robots_status,
            rate_limit_status=rate_limit_status,
        )

        return {
            "dns": dns_status,
            "tcp": tcp_status,
            "http": http_status,
            "robots": robots_status,
            "rate_limit": rate_limit_status,
            "overall": overall,
            "blocking_reason": blocking_reason,
        }

    def _test_dns_resolution(self, domain: str) -> str:
        if not domain:
            return "DNS_DEAD"
        try:
            socket.getaddrinfo(domain, None)
            return "OK"
        except socket.gaierror:
            return "DNS_DEAD"
        except OSError:
            return "DNS_DEAD"

    def _test_tcp_connectivity(self, domain: str, scheme: str) -> str:
        if not domain:
            return "FIREWALL"

        preferred_port = 443 if scheme == "https" else 80
        ports = [preferred_port] + ([80] if preferred_port == 443 else [443])

        for port in ports:
            try:
                with socket.create_connection((domain, port), timeout=3.0):
                    return "OK"
            except OSError:
                continue
        return "FIREWALL"

    def _test_http_response(self, url: str) -> dict:
        start = time.monotonic()
        try:
            response = self.session.head(
                url,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
                allow_redirects=True,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            status_code = int(response.status_code)

            if "cf-ray" in {k.lower(): v for k, v in response.headers.items()}:
                return {
                    "status": "BLOCKED",
                    "code": status_code,
                    "response_ms": elapsed_ms,
                }

            if status_code in {403, 429}:
                return {
                    "status": "BLOCKED",
                    "code": status_code,
                    "response_ms": elapsed_ms,
                }
            if 200 <= status_code < 400:
                return {
                    "status": "OK",
                    "code": status_code,
                    "response_ms": elapsed_ms,
                }
            return {
                "status": "HTTP_ERROR",
                "code": status_code,
                "response_ms": elapsed_ms,
            }

        except requests.exceptions.SSLError:
            return {
                "status": "SSL_ERROR",
                "code": None,
                "response_ms": int((time.monotonic() - start) * 1000),
            }
        except requests.exceptions.Timeout:
            return {
                "status": "TIMEOUT",
                "code": None,
                "response_ms": int((time.monotonic() - start) * 1000),
            }
        except requests.exceptions.RequestException:
            return {
                "status": "HTTP_ERROR",
                "code": None,
                "response_ms": int((time.monotonic() - start) * 1000),
            }

    def _test_robots_compliance(
        self, scheme: str, netloc: str, target_path: str
    ) -> dict:
        if not scheme or not netloc:
            return {"status": "NO_ROBOTS_FILE", "crawl_delay": 0}

        robots_url = f"{scheme}://{netloc}/robots.txt"
        try:
            response = self.session.get(
                robots_url,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
                allow_redirects=True,
            )
            if response.status_code >= 400:
                return {"status": "NO_ROBOTS_FILE", "crawl_delay": 0}

            rp = RobotFileParser()
            rp.parse((response.text or "").splitlines())
            probe_url = f"{scheme}://{netloc}{target_path or '/'}"
            allowed = rp.can_fetch(self.user_agent, probe_url)
            crawl_delay = rp.crawl_delay(self.user_agent)
            if crawl_delay is None:
                crawl_delay = rp.crawl_delay("*")

            if allowed:
                return {
                    "status": "ALLOWED",
                    "crawl_delay": int(crawl_delay or 0),
                }
            return {
                "status": "DISALLOWED",
                "crawl_delay": int(crawl_delay or 0),
            }
        except requests.exceptions.RequestException:
            return {"status": "NO_ROBOTS_FILE", "crawl_delay": 0}
        except Exception:
            logger.debug("robots_validation_failed", exc_info=True)
            return {"status": "NO_ROBOTS_FILE", "crawl_delay": 0}

    def _test_rate_limit_detection(self, url: str) -> str:
        latencies = []
        cf_detected = False

        for _ in range(3):
            start = time.monotonic()
            try:
                response = self.session.get(
                    url,
                    timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
                    allow_redirects=True,
                )
                latency = time.monotonic() - start
                latencies.append(latency)

                if response.status_code == 429:
                    return "RATE_LIMITED"
                if "cf-ray" in {k.lower(): v for k, v in response.headers.items()}:
                    cf_detected = True
            except requests.exceptions.Timeout:
                latencies.append(self.CONNECT_TIMEOUT + self.READ_TIMEOUT)
            except requests.exceptions.RequestException:
                latencies.append(self.CONNECT_TIMEOUT + self.READ_TIMEOUT)

        if cf_detected:
            return "ANTI_BOT"

        if (
            len(latencies) == 3
            and latencies[0] > 0
            and latencies[2] > (latencies[0] * 2)
        ):
            return "THROTTLING"

        return "OK"

    @staticmethod
    def _compute_overall(
        *,
        dns_status: str,
        tcp_status: str,
        http_status: dict,
        robots_status: dict,
        rate_limit_status: str,
    ) -> tuple[str, str | None]:
        red_map = [
            (dns_status == "DNS_DEAD", "DNS_DEAD"),
            (tcp_status == "FIREWALL", "FIREWALL"),
            (http_status.get("status") == "SSL_ERROR", "SSL_ERROR"),
            (http_status.get("status") == "BLOCKED", "CLOUDFLARE"),
            (robots_status.get("status") == "DISALLOWED", "DISALLOWED"),
            (rate_limit_status == "ANTI_BOT", "ANTI_BOT"),
            (rate_limit_status == "RATE_LIMITED", "RATE_LIMITED"),
        ]

        for is_red, reason in red_map:
            if is_red:
                return "RED", reason

        if robots_status.get("crawl_delay", 0) > 0:
            return "YELLOW", None
        if rate_limit_status == "THROTTLING":
            return "YELLOW", None
        if http_status.get("status") in {"HTTP_ERROR", "TIMEOUT"}:
            return "YELLOW", http_status.get("status")

        return "GREEN", None
