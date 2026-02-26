"""
Base scraper module providing the abstract foundation for all web scrapers.
"""

import logging
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from dateutil import parser as date_parser
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseScraper(ABC):
    """Abstract base class for all platform web scrapers."""

    name: str = "Base Scraper"
    category: str = "unknown"

    def __init__(self):
        self.results: list = []
        self.errors: list = []
        self.items_created: int = 0
        self.items_skipped: int = 0
        self._system_user = None
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; NLPPlatformBot/1.0; "
                    "+https://github.com/nlp-platform; research purposes)"
                ),
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
            self.errors.append(f"Scraper error: {exc}")
            logger.exception("Scraper %s failed", self.name)
        finally:
            self._enable_es_indexing()

        return {
            "scraper": self.name,
            "category": self.category,
            "items_created": self.items_created,
            "items_skipped": self.items_skipped,
            "items_found": self.items_created + self.items_skipped,
            "errors": self.errors,
            "results": self.results,
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
    # Helpers – HTTP
    # ------------------------------------------------------------------

    def safe_request(self, url: str, method: str = "GET", **kwargs):
        """Perform an HTTP request with timeout and error handling."""
        try:
            timeout = kwargs.pop("timeout", 30)
            fn = self.session.get if method.upper() == "GET" else self.session.post
            response = fn(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            self.errors.append(f"Request to {url} failed: {exc}")
            logger.error("Request to %s failed: %s", url, exc)
            return None

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
