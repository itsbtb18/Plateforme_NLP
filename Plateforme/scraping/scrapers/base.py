"""
Base scraper module providing the abstract foundation for all web scrapers.
"""

import logging
import random
import time
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from dateutil import parser as date_parser
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

# ── User-Agent rotation pool ────────────────────────────────────────
_USER_AGENTS = [
    (
        "Mozilla/5.0 (compatible; NLPPlatformBot/1.0; "
        "+https://github.com/nlp-platform; research purposes)"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.3 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 "
        "Firefox/125.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
]


class BaseScraper(ABC):
    """Abstract base class for all platform web scrapers.

    Phase 5 enhancements
    --------------------
    * **Retry with exponential back-off** — ``safe_request`` retries
      transient failures (429, 5xx, connection errors) automatically.
    * **User-Agent rotation** — each request randomly picks a UA string.
    * **Configurable timeout** — ``DEFAULT_TIMEOUT`` class attribute.
    * **Circuit breaker** — ``check_source`` / ``report_*`` methods
      read/write the ``ScrapingSourceHealth`` model.
    * **Structured error logging** — ``_log_error`` produces consistent
      dicts in ``self.structured_errors``.
    * **Per-source tracking** — every HTTP call is tied to a source_name
      so health metrics accumulate.
    """

    name: str = "Base Scraper"
    category: str = "unknown"

    # Configurable defaults (sub-classes may override)
    DEFAULT_TIMEOUT: int = 30        # seconds
    MAX_RETRIES: int = 3             # retries on transient HTTP errors
    BACKOFF_BASE: float = 2.0        # base seconds for exponential backoff
    BACKOFF_MAX: float = 60.0        # cap for backoff sleep

    def __init__(self):
        self.results: list = []
        self.errors: list = []
        self.structured_errors: list[dict] = []
        self.items_created: int = 0
        self.items_skipped: int = 0
        self._system_user = None
        self._health_cache: dict = {}  # source_name → ScrapingSourceHealth

        self.session = requests.Session()
        self._rotate_user_agent()
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape(self):
        """Execute the scraping logic.  Must be implemented by each sub-class."""

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute the full scraping pipeline and return a summary dict."""
        logger.info("Starting scraper: %s", self.name)
        self._disable_es_indexing()
        try:
            self.scrape()
        except Exception as exc:
            self._log_error("scraper_crash", str(exc), source=self.name)
            logger.exception("Scraper %s failed", self.name)
        finally:
            self._enable_es_indexing()

        # Phase 6: compute domain classification & relevance scores
        intelligence_summary = self._run_intelligence()

        return {
            "scraper": self.name,
            "category": self.category,
            "items_created": self.items_created,
            "items_skipped": self.items_skipped,
            "items_found": self.items_created + self.items_skipped,
            "errors": self.errors,
            "structured_errors": self.structured_errors,
            "results": self.results,
            "intelligence": intelligence_summary,
        }

    # ------------------------------------------------------------------
    # Helpers – Elasticsearch signal management
    # ------------------------------------------------------------------

    def _disable_es_indexing(self):
        """Temporarily monkey-patch the ES registry so saves don't trigger indexing."""
        try:
            from django_elasticsearch_dsl.registries import registry

            self._original_es_update = registry.update
            self._original_es_delete = registry.delete
            registry.update = lambda *a, **kw: None
            registry.delete = lambda *a, **kw: None
            logger.debug("Elasticsearch indexing disabled for scraping")
        except ImportError:
            pass

    def _enable_es_indexing(self):
        """Restore the ES registry's original update/delete methods."""
        try:
            from django_elasticsearch_dsl.registries import registry

            if hasattr(self, "_original_es_update"):
                registry.update = self._original_es_update
            if hasattr(self, "_original_es_delete"):
                registry.delete = self._original_es_delete
            logger.debug("Elasticsearch indexing re-enabled")
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Helpers – system user
    # ------------------------------------------------------------------

    def get_system_user(self):
        """Return (or lazily create) the platform's system-scraper user."""
        if self._system_user is not None:
            return self._system_user

        try:
            user = User.objects.get(email="system@nlp-platform.local")
        except User.DoesNotExist:
            user = User(
                email="system@nlp-platform.local",
                full_name_en="System Scraper",
                full_name_ar="نظام الاستخراج",
                full_name="System Scraper",
                is_active=True,
                is_staff=False,
                is_email_verified=True,
                status="active",
            )
            user.set_unusable_password()
            # bulk_create avoids post_save signals (ES indexing)
            User.objects.bulk_create([user])
            user = User.objects.get(email="system@nlp-platform.local")
            logger.info("Created system user for web scraping")

        self._system_user = user
        return user

    # ------------------------------------------------------------------
    # Helpers – related objects
    # ------------------------------------------------------------------

    def get_or_create_country(self, name_en: str, code: str = "", name_ar: str = ""):
        """Return an ``institutions.Country``, creating it when necessary."""
        from institutions.models import Country

        code = (code or name_en[:2]).upper()[:2]
        country, _ = Country.objects.get_or_create(
            code=code,
            defaults={
                "name_en": name_en,
                "name_ar": name_ar or name_en,
            },
        )
        return country

    def get_or_create_institution(self, name: str, **kwargs):
        """Return an ``institutions.Institution``, creating it when necessary."""
        from institutions.models import Institution

        inst = Institution.objects.filter(name_en__iexact=name).first()
        if inst:
            return inst

        country = kwargs.get("country")
        if country is None:
            country = self.get_or_create_country("International", "XX")

        city = kwargs.get("city", "")
        description = kwargs.get("description", "")
        if not description:
            description = (
                f"{name} is a research institution active in natural language "
                f"processing and computational linguistics."
            )

        # Build address from city + country
        country_name = getattr(country, "name_en", "")
        address = f"{city}, {country_name}" if city else country_name

        try:
            inst = Institution.objects.create(
                name=name,
                name_en=name,
                name_ar=kwargs.get("name_ar", name),
                acronym=kwargs.get("acronym", ""),
                type=kwargs.get("inst_type", "University"),
                country=country,
                city_en=city,
                city=city,
                city_ar=city,
                website=kwargs.get("website", ""),
                email=kwargs.get("email", ""),
                phone=kwargs.get("phone", ""),
                address=address,
                address_en=address,
                address_ar=address,
                description_en=description,
                description=description,
                description_ar=description,
                created_by=self.get_system_user(),
            )
            return inst
        except Exception as exc:
            logger.error("Error creating institution %s: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Helpers – HTTP (with retry / backoff / circuit breaker)
    # ------------------------------------------------------------------

    def _rotate_user_agent(self):
        """Pick a random User-Agent for the session."""
        self.session.headers["User-Agent"] = random.choice(_USER_AGENTS)

    def safe_request(
        self,
        url: str,
        method: str = "GET",
        source_name: str | None = None,
        **kwargs,
    ):
        """HTTP request with retry, exponential back-off, and health tracking.

        Parameters
        ----------
        url : str
        method : str
        source_name : str | None
            Logical source name for health tracking.  Falls back to
            the URL's domain if not provided.
        **kwargs
            Passed through to ``requests.Session.request``.  The key
            ``timeout`` defaults to ``self.DEFAULT_TIMEOUT``.
        """
        from urllib.parse import urlparse

        if source_name is None:
            source_name = urlparse(url).netloc or self.name

        # Circuit breaker check
        if not self.check_source(source_name, url):
            msg = f"Circuit open for {source_name} — skipping {url}"
            self._log_error("circuit_open", msg, source=source_name, url=url)
            return None

        timeout = kwargs.pop("timeout", self.DEFAULT_TIMEOUT)
        max_retries = kwargs.pop("max_retries", self.MAX_RETRIES)
        last_exc = None

        for attempt in range(1, max_retries + 1):
            # Rotate UA per attempt
            self._rotate_user_agent()

            t0 = time.monotonic()
            try:
                fn = self.session.get if method.upper() == "GET" else self.session.post
                response = fn(url, timeout=timeout, **kwargs)

                elapsed = time.monotonic() - t0

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 0)) + 2
                    sleep = max(
                        retry_after,
                        min(self.BACKOFF_BASE * (2 ** (attempt - 1)), self.BACKOFF_MAX),
                    )
                    self._log_error(
                        "rate_limited", f"429 from {url}",
                        source=source_name, url=url,
                        extra={"attempt": attempt, "sleep": sleep},
                    )
                    time.sleep(sleep)
                    continue

                if response.status_code >= 500:
                    sleep = min(
                        self.BACKOFF_BASE * (2 ** (attempt - 1)), self.BACKOFF_MAX,
                    )
                    self._log_error(
                        "server_error",
                        f"{response.status_code} from {url}",
                        source=source_name, url=url,
                        extra={"attempt": attempt, "sleep": sleep},
                    )
                    time.sleep(sleep)
                    continue

                response.raise_for_status()

                # Success → record health
                self.report_success(source_name, url, elapsed)
                return response

            except requests.ConnectionError as exc:
                elapsed = time.monotonic() - t0
                last_exc = exc
                sleep = min(
                    self.BACKOFF_BASE * (2 ** (attempt - 1)), self.BACKOFF_MAX,
                )
                self._log_error(
                    "connection_error", str(exc),
                    source=source_name, url=url,
                    extra={"attempt": attempt, "sleep": sleep},
                )
                time.sleep(sleep)

            except requests.Timeout as exc:
                elapsed = time.monotonic() - t0
                last_exc = exc
                sleep = min(
                    self.BACKOFF_BASE * (2 ** (attempt - 1)), self.BACKOFF_MAX,
                )
                self._log_error(
                    "timeout", str(exc),
                    source=source_name, url=url,
                    extra={"attempt": attempt, "timeout": timeout, "sleep": sleep},
                )
                time.sleep(sleep)

            except requests.RequestException as exc:
                last_exc = exc
                self._log_error(
                    "request_error", str(exc),
                    source=source_name, url=url,
                    extra={"attempt": attempt},
                )
                break  # Non-transient — don't retry

        # All retries exhausted
        error_msg = f"Request to {url} failed after {max_retries} attempts: {last_exc}"
        self.errors.append(error_msg)
        self.report_failure(source_name, url, str(last_exc or "unknown"))
        return None

    # ------------------------------------------------------------------
    # Helpers – circuit breaker & source health
    # ------------------------------------------------------------------

    def _get_health(self, source_name: str, base_url: str = "") -> "ScrapingSourceHealth":
        """Return (or create) the health record for a source, with caching."""
        if source_name in self._health_cache:
            return self._health_cache[source_name]

        from scraping.models import ScrapingSourceHealth

        health, _ = ScrapingSourceHealth.objects.get_or_create(
            category=self.category,
            source_name=source_name,
            defaults={"base_url": base_url},
        )
        self._health_cache[source_name] = health
        return health

    def check_source(self, source_name: str, base_url: str = "") -> bool:
        """Return True if the source's circuit breaker allows a request."""
        health = self._get_health(source_name, base_url)
        return health.is_available()

    def report_success(
        self, source_name: str, base_url: str = "", response_time: float | None = None,
    ):
        """Report a successful request to the health tracker."""
        health = self._get_health(source_name, base_url)
        health.record_success(response_time)

    def report_failure(self, source_name: str, base_url: str = "", error: str = ""):
        """Report a failed request to the health tracker."""
        health = self._get_health(source_name, base_url)
        health.record_failure(error)

    # ------------------------------------------------------------------
    # Helpers – structured error logging
    # ------------------------------------------------------------------

    def _log_error(
        self,
        error_type: str,
        message: str,
        *,
        source: str = "",
        url: str = "",
        extra: dict | None = None,
    ):
        """Record a structured error entry and log it."""
        entry = {
            "type": error_type,
            "message": message,
            "source": source or self.name,
            "url": url,
            "category": self.category,
            "timestamp": timezone.now().isoformat(),
        }
        if extra:
            entry["extra"] = extra

        self.structured_errors.append(entry)
        logger.warning(
            "[%s] %s — %s (source=%s url=%s)",
            self.category, error_type, message, source or self.name, url,
        )

    # ------------------------------------------------------------------
    # Helpers – data parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_date(date_str, default=None):
        """Best-effort date parsing from an arbitrary string."""
        if not date_str:
            return default
        try:
            dt = date_parser.parse(date_str, fuzzy=True)
            return dt.date() if isinstance(dt, datetime) else dt
        except (ValueError, OverflowError):
            return default

    @staticmethod
    def truncate(text: str, max_len: int = 200) -> str:
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove excessive whitespace from text."""
        if not text:
            return ""
        import re

        return re.sub(r"\s+", " ", text).strip()

    # ------------------------------------------------------------------
    # Phase 6: Intelligence — domain classification & scoring
    # ------------------------------------------------------------------

    def _run_intelligence(self) -> dict:
        """Classify and score all items created during this scrape run.

        Iterates over ``self.results`` (populated by sub-class scrapers)
        and creates ``ScrapedItemMeta`` records with domain scores and
        relevance scores.

        Returns a summary dict for the run report.
        """
        try:
            from scraping.intelligence import (
                classify_domain,
                classify_domain_primary,
                compute_relevance_score,
            )
            from scraping.models import ScrapedItemMeta
        except Exception as exc:
            logger.debug("Intelligence module not available: %s", exc)
            return {"status": "skipped", "reason": str(exc)}

        scored = 0
        domain_counts: dict[str, int] = {}
        avg_score = 0.0

        for item in self.results:
            title = item.get("title", "")
            if not title:
                continue

            # Build text for classification
            text = f"{title} {item.get('description', '')} {item.get('type', '')}"

            # Classify
            d_scores = classify_domain(text)
            primary = classify_domain_primary(text)

            # Score
            score = compute_relevance_score(
                text=text,
                has_description=bool(item.get("description") or item.get("type")),
                has_website=bool(item.get("url")),
                has_arabic=any(ord(c) > 0x0600 and ord(c) < 0x06FF for c in text),
                domain_scores=d_scores,
            )

            # Store metadata
            try:
                ScrapedItemMeta.objects.update_or_create(
                    category=self.category,
                    item_title=title[:300],
                    defaults={
                        "domain_scores": d_scores,
                        "primary_domain": primary,
                        "relevance_score": score,
                    },
                )
            except Exception:
                pass  # Non-critical — don't fail the scrape

            scored += 1
            avg_score += score
            domain_counts[primary] = domain_counts.get(primary, 0) + 1

        avg_score = round(avg_score / max(scored, 1), 1)

        summary = {
            "status": "completed",
            "items_scored": scored,
            "avg_relevance_score": avg_score,
            "domain_distribution": domain_counts,
        }
        logger.info(
            "Intelligence: scored %d items, avg=%.1f, domains=%s",
            scored, avg_score, domain_counts,
        )
        return summary
