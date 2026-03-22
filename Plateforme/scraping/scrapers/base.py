"""
Base scraper module providing the abstract foundation for all web scrapers.
"""

import logging
import os
import random
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from urllib.parse import urlparse
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
    ("Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"),
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
    DEFAULT_TIMEOUT: int = 30  # seconds
    MAX_RETRIES: int = 3  # retries on transient HTTP errors
    BACKOFF_BASE: float = 2.0  # base seconds for exponential backoff
    BACKOFF_MAX: float = 60.0  # cap for backoff sleep

    def __init__(self):
        self.results: list = []
        self.errors: list = []
        self.structured_errors: list[dict] = []
        self.items_created: int = 0
        self.items_skipped: int = 0
        self.validation_stats = {
            "passed": 0,
            "failed_date": 0,
            "failed_fields": 0,
            "failed_freshness": 0,
            "auto_filled": 0,
        }
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
        logger.info(
            "scraper_started",
            extra={
                "category": self.category,
                "source_name": self.name,
            },
        )
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

        summary = {
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
        summary["validation_stats"] = getattr(self, "validation_stats", {})
        return summary

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
        """
        Get or create a dedicated system scraper user.
        Never returns None. Always creates if missing.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        SYSTEM_EMAIL = "scraper-bot@nlp-platform.local"
        SYSTEM_NAME = "System Scraper Bot"

        if hasattr(self, "_system_user") and self._system_user:
            return self._system_user

        try:
            user = User.objects.filter(email=SYSTEM_EMAIL).first()

            if not user:
                # Create the system user safely
                try:
                    user = User.objects.create_user(
                        email=SYSTEM_EMAIL,
                        password=None,
                        full_name=SYSTEM_NAME,
                        full_name_en=SYSTEM_NAME,
                        full_name_ar="روبوت نظام الاستخراج",
                    )
                    user.is_active = True
                    user.is_staff = False
                    user.is_superuser = False
                    if hasattr(user, "is_verified"):
                        user.is_verified = True
                    if hasattr(user, "is_email_verified"):
                        user.is_email_verified = True
                    user.save()
                except Exception:
                    # If create_user fails due to custom
                    # manager requirements, try get_or_create
                    # with minimal fields
                    user = User.objects.filter(is_superuser=True).first()

                    if not user:
                        # Absolute last resort: raise clearly
                        raise RuntimeError(
                            "Cannot find or create system user "
                            "for scraping. Please run: "
                            "python manage.py createsuperuser"
                        )

            self._system_user = user
            return self._system_user

        except Exception as e:
            self._log_error("get_system_user", str(e), "system_user_init")
            # Try superuser fallback
            User = get_user_model()
            fallback = User.objects.filter(is_superuser=True).first()
            if fallback:
                self._system_user = fallback
                return fallback
            raise RuntimeError(
                f"Cannot get system user: {e}. Create a superuser first."
            )

    # ------------------------------------------------------------------
    # Helpers – RSS / Atom feeds
    # ------------------------------------------------------------------

    def get_rss_scraper(self):
        from scraping.scrapers.rss_scraper import RSSFeedScraper

        return RSSFeedScraper(self)

    def _is_download_enabled(self) -> bool:
        raw = os.getenv("SCRAPING_DOWNLOAD_ENABLED", "true").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    def _max_concurrent_downloads(self) -> int:
        raw = os.getenv("SCRAPING_MAX_CONCURRENT_DOWNLOADS", "3").strip()
        try:
            value = int(raw)
        except ValueError:
            value = 3
        return max(1, value)

    @staticmethod
    def _coerce_url_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            urls = [str(v).strip() for v in value if str(v).strip()]
        else:
            text = str(value).strip()
            urls = [text] if text else []
        deduped = []
        seen = set()
        for url in urls:
            if not url:
                continue
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    @staticmethod
    def _is_probable_pdf_url(url: str) -> bool:
        lower = (url or "").lower()
        return ".pdf" in lower or "arxiv.org/pdf/" in lower

    def _collect_page_media_urls(self, page_url: str, category: str) -> dict:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        result = {"images": [], "pdfs": []}
        if not page_url:
            return result

        response = self.safe_request(
            page_url,
            timeout=12,
            source_name=f"media:{category}",
        )
        if not response:
            return result

        soup = BeautifulSoup(response.text or "", "html.parser")
        images: list[str] = []
        pdfs: list[str] = []

        def add_image(url: str):
            clean = (url or "").strip()
            if not clean:
                return
            images.append(urljoin(page_url, clean))

        def add_pdf(url: str):
            clean = (url or "").strip()
            if not clean:
                return
            pdfs.append(urljoin(page_url, clean))

        og_image = soup.select_one("meta[property='og:image']")
        if og_image and og_image.get("content"):
            add_image(og_image.get("content"))

        twitter_image = soup.select_one("meta[name='twitter:image']")
        if twitter_image and twitter_image.get("content"):
            add_image(twitter_image.get("content"))

        if category == "institutions":
            logo_like = soup.select_one(
                "img[src*='logo' i], img[alt*='logo' i], img[class*='logo' i]"
            )
            if logo_like and logo_like.get("src"):
                add_image(logo_like.get("src"))

        first_image = soup.select_one("article img, .content img, main img, img")
        if first_image and first_image.get("src"):
            width_attr = first_image.get("width")
            try:
                width_value = int(str(width_attr)) if width_attr else 999
            except ValueError:
                width_value = 999
            if category != "news" or width_value >= 200:
                add_image(first_image.get("src"))

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            text = self._normalize_text(anchor.get_text(" ", strip=True))
            if not href:
                continue

            if self._is_probable_pdf_url(href):
                add_pdf(href)
                continue

            if category == "events":
                if any(
                    token in text
                    for token in [
                        "programme",
                        "brochure",
                        "call for papers",
                        "appel a communications",
                        "appel à communications",
                        "cfa",
                    ]
                ):
                    add_pdf(href)

            if category == "tools":
                if any(token in text for token in ["documentation", "paper", "arxiv"]):
                    add_pdf(href)

            if category == "courses":
                if any(
                    token in text for token in ["syllabus", "curriculum", "programme"]
                ):
                    add_pdf(href)

        link_icon = soup.select_one("link[rel='icon'], link[rel='shortcut icon']")
        if link_icon and link_icon.get("href"):
            add_image(link_icon.get("href"))

        result["images"] = list(dict.fromkeys(images))
        result["pdfs"] = list(dict.fromkeys(pdfs))
        return result

    def _resolve_media_candidates(self, item_data: dict, category: str) -> dict:
        from urllib.parse import urlparse

        image_urls: list[str] = []
        pdf_urls: list[str] = []

        image_urls.extend(self._coerce_url_list(item_data.get("thumbnail_url")))
        image_urls.extend(self._coerce_url_list(item_data.get("image_url")))
        image_urls.extend(self._coerce_url_list(item_data.get("logo_url")))
        image_urls.extend(self._coerce_url_list(item_data.get("banner_image_url")))

        pdf_urls.extend(self._coerce_url_list(item_data.get("pdf_url")))
        pdf_urls.extend(self._coerce_url_list(item_data.get("syllabus_file_url")))
        pdf_urls.extend(self._coerce_url_list(item_data.get("documentation_pdf_url")))
        pdf_urls.extend(self._coerce_url_list(item_data.get("pdf_attachments")))

        page_urls = []
        page_urls.extend(self._coerce_url_list(item_data.get("website")))
        page_urls.extend(self._coerce_url_list(item_data.get("source_url")))
        page_urls.extend(self._coerce_url_list(item_data.get("access_link")))
        page_urls.extend(self._coerce_url_list(item_data.get("course_url")))

        for page_url in list(dict.fromkeys(page_urls))[:3]:
            try:
                found = self._collect_page_media_urls(page_url, category)
                image_urls.extend(found.get("images", []))
                pdf_urls.extend(found.get("pdfs", []))
            except Exception as exc:
                self._log_error(
                    "media_discovery",
                    str(exc),
                    source=category,
                    url=page_url,
                )

        if category == "news":
            arxiv_id = (item_data.get("arxiv_id") or "").strip()
            if arxiv_id:
                arxiv_abs_url = f"https://arxiv.org/abs/{arxiv_id}"
                try:
                    found = self._collect_page_media_urls(arxiv_abs_url, category)
                    image_urls.extend(found.get("images", []))
                except Exception:
                    pass
                pdf_urls.append(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

        if category == "tools":
            github_url = (item_data.get("github_url") or "").strip()
            parsed = urlparse(github_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 1:
                owner = path_parts[0]
                api_resp = self.safe_request(
                    f"https://api.github.com/users/{owner}",
                    source_name="media:tools:github",
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=10,
                )
                if api_resp is not None:
                    try:
                        payload = api_resp.json()
                        owner_id = payload.get("id")
                        if owner_id:
                            image_urls.append(
                                f"https://avatars.githubusercontent.com/u/{owner_id}"
                            )
                        avatar_url = payload.get("avatar_url")
                        if avatar_url:
                            image_urls.append(str(avatar_url))
                    except Exception:
                        pass

        if category in {"tools", "institutions"}:
            for key in ("website", "access_link", "source_url"):
                for base in self._coerce_url_list(item_data.get(key)):
                    parsed = urlparse(base)
                    if parsed.scheme and parsed.netloc:
                        image_urls.append(
                            f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
                        )

        if category == "courses":
            course_url = (
                item_data.get("course_url") or item_data.get("access_link") or ""
            ).strip()
            playlist_match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", course_url)
            video_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", course_url)
            if video_match:
                video_id = video_match.group(1)
                image_urls.append(
                    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                )
            elif playlist_match:
                image_urls.extend(
                    self._coerce_url_list(item_data.get("youtube_thumbnail_url"))
                )

        return {
            "images": list(dict.fromkeys([u for u in image_urls if u])),
            "pdfs": list(dict.fromkeys([u for u in pdf_urls if u])),
        }

    def _download_media(self, item_data: dict, category: str) -> dict:
        """Download item media assets in parallel; never raise.

        Adds local path keys:
          - image_local_path
          - pdf_local_path
        """
        if not isinstance(item_data, dict):
            return item_data

        if not self._is_download_enabled():
            item_data["image_local_path"] = item_data.get("image_local_path") or ""
            item_data["pdf_local_path"] = item_data.get("pdf_local_path") or ""
            return item_data

        try:
            from scraping.file_downloader import download_file

            media = self._resolve_media_candidates(item_data, category)
            image_candidates = media.get("images", [])
            pdf_candidates = media.get("pdfs", [])

            tasks = []
            with ThreadPoolExecutor(
                max_workers=self._max_concurrent_downloads()
            ) as pool:
                for url in image_candidates:
                    tasks.append(
                        (
                            "image",
                            url,
                            pool.submit(
                                download_file,
                                url,
                                category,
                                item_name=self._item_display_name(item_data),
                                file_type="image",
                            ),
                        )
                    )
                for url in pdf_candidates:
                    tasks.append(
                        (
                            "pdf",
                            url,
                            pool.submit(
                                download_file,
                                url,
                                category,
                                item_name=self._item_display_name(item_data),
                                file_type="document",
                            ),
                        )
                    )

                image_local_path = ""
                image_content = None
                pdf_local_path = ""
                pdf_content = None

                future_to_meta = {
                    future: (kind, src_url) for kind, src_url, future in tasks
                }

                for future in as_completed(future_to_meta):
                    kind, src_url = future_to_meta[future]
                    try:
                        content_file, filename, _mime = future.result()
                    except Exception as exc:
                        self._log_error(
                            "media_download",
                            str(exc),
                            source=category,
                            url=src_url,
                        )
                        continue

                    if not filename:
                        continue

                    if kind == "image" and not image_local_path:
                        image_local_path = filename
                        image_content = content_file
                    if kind == "pdf" and not pdf_local_path:
                        pdf_local_path = filename
                        pdf_content = content_file

                item_data["image_local_path"] = image_local_path
                item_data["image_content_file"] = image_content
                item_data["pdf_local_path"] = pdf_local_path
                item_data["pdf_content_file"] = pdf_content

        except Exception as exc:
            self._log_error(
                "media_pipeline",
                str(exc),
                source=category,
            )
            item_data.setdefault("image_local_path", "")
            item_data.setdefault("pdf_local_path", "")

        return item_data

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

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip().lower()

    @staticmethod
    def _normalize_url(value: str, strip_www: bool = False) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()
        if strip_www and netloc.startswith("www."):
            netloc = netloc[4:]
        path = (parsed.path or "").rstrip("/")
        return f"{scheme}://{netloc}{path}"

    @staticmethod
    def _title_similarity(left: str, right: str) -> float:
        return SequenceMatcher(
            None,
            BaseScraper._normalize_text(left),
            BaseScraper._normalize_text(right),
        ).ratio()

    @staticmethod
    def _extract_instructor(value: str) -> str:
        text = value or ""
        match = re.search(r"(?:instructor|teacher)\s*[:\-]\s*([^\n\r]+)", text, re.I)
        if not match:
            return ""
        return BaseScraper._normalize_text(match.group(1))

    @staticmethod
    def _item_display_name(item_data: dict) -> str:
        for key in ("title_en", "title", "name_en", "name"):
            value = (item_data.get(key) or "").strip()
            if value:
                return value
        return "untitled"

    def _set_duplicate_match(self, existing_obj):
        self._last_duplicate_match_id = str(getattr(existing_obj, "id", ""))

    def _record_duplicate_skip(self, category: str, item_data: dict, reason: str):
        item_label = self._item_display_name(item_data)
        matched_id = getattr(self, "_last_duplicate_match_id", "")
        reason_code = self._normalize_skip_reason(reason)
        logger.info(
            "item_skipped",
            extra={
                "category": category,
                "source_name": self.name,
                "item_title": item_label,
                "item_id": matched_id or "unknown",
                "skip_reason": reason_code,
            },
        )
        try:
            from scraping.models import ScrapedItemMeta

            ScrapedItemMeta.objects.update_or_create(
                category=category,
                item_title=item_label[:300],
                defaults={
                    "item_id": matched_id,
                    "skip_reason": reason_code,
                    "was_skipped": True,
                },
            )
        except Exception as exc:
            self._log_error("dedup_skip_meta", str(exc), source=item_label)

    @staticmethod
    def _normalize_skip_reason(reason: str) -> str:
        lowered = BaseScraper._normalize_text(reason or "")
        if "doi" in lowered:
            return "dedup_doi"
        if "arxiv" in lowered:
            return "dedup_arxiv"
        if "ror" in lowered:
            return "dedup_ror"
        if "embed" in lowered:
            return "dedup_embedding"
        if "url" in lowered or "website" in lowered or "link" in lowered:
            return "dedup_url"
        if "name" in lowered or "title" in lowered or "exact" in lowered:
            return "dedup_name"
        return "dedup_similarity"

    def _dedup_event(self, item_data: dict) -> tuple[bool, str]:
        from events.models import Event

        website_url = (
            item_data.get("website_url") or item_data.get("website") or ""
        ).strip()
        if website_url:
            existing = Event.objects.filter(website__iexact=website_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "event website_url exact match"

        organizer = item_data.get("organizer")
        start_date = item_data.get("start_date")
        end_date = item_data.get("end_date") or start_date
        if organizer and start_date and end_date:
            start_window = start_date - timedelta(days=3)
            end_window = end_date + timedelta(days=3)
            queryset = Event.objects.all()
            if hasattr(organizer, "id"):
                queryset = queryset.filter(organizer=organizer)
            else:
                organizer_name = self._normalize_text(str(organizer))
                queryset = queryset.filter(organizer__name_en__iexact=organizer_name)
            existing = queryset.filter(
                start_date__lte=end_window,
                end_date__gte=start_window,
            ).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "event same organizer + overlapping date range"

        candidate_title = item_data.get("title_en") or item_data.get("title") or ""
        if candidate_title:
            for event in Event.objects.only("id", "title", "title_en"):
                existing_title = event.title_en or event.title
                if self._title_similarity(candidate_title, existing_title) >= 0.85:
                    self._set_duplicate_match(event)
                    return True, "event title similarity >= 85%"

        return False, ""

    def _dedup_tool(self, item_data: dict) -> tuple[bool, str]:
        from resources.models import NLPTool

        github_url = (item_data.get("github_url") or "").strip()
        if github_url:
            existing = NLPTool.objects.filter(github_url__iexact=github_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool github_url exact match"

        access_link = (item_data.get("access_link") or "").strip()
        if access_link:
            existing = NLPTool.objects.filter(access_link__iexact=access_link).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool access_link exact match"

        item_name = self._normalize_text(
            item_data.get("title_en") or item_data.get("title")
        )
        if item_name:
            for tool in NLPTool.objects.only("id", "title", "title_en"):
                existing_name = self._normalize_text(tool.title_en or tool.title)
                if existing_name == item_name:
                    self._set_duplicate_match(tool)
                    return True, "tool name exact match"

        if item_name:
            for tool in NLPTool.objects.only("id", "title", "title_en"):
                existing_name = tool.title_en or tool.title
                if self._title_similarity(item_name, existing_name) >= 0.90:
                    self._set_duplicate_match(tool)
                    return True, "tool name similarity >= 90%"

        return False, ""

    def _dedup_news(self, item_data: dict) -> tuple[bool, str]:
        from QA.models import Post

        arxiv_id = (item_data.get("arxiv_id") or "").strip()
        if arxiv_id:
            existing = Post.objects.filter(arxiv_id__iexact=arxiv_id).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "news arxiv_id exact match"

        doi = (item_data.get("doi") or "").strip()
        if doi:
            existing = Post.objects.filter(doi__iexact=doi).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "news doi exact match"

        source_url = self._normalize_url(item_data.get("source_url"))
        if source_url:
            source_url_noslash = source_url.rstrip("/")
            for post in Post.objects.only("id", "source_url"):
                if (
                    self._normalize_url(post.source_url).rstrip("/")
                    == source_url_noslash
                ):
                    self._set_duplicate_match(post)
                    return True, "news source_url exact match"

        candidate_title = item_data.get("title_en") or item_data.get("title") or ""
        if candidate_title:
            for post in Post.objects.only("id", "title", "title_en"):
                existing_title = post.title_en or post.title
                if self._title_similarity(candidate_title, existing_title) >= 0.85:
                    self._set_duplicate_match(post)
                    return True, "news title similarity >= 85%"

        return False, ""

    def _dedup_course(self, item_data: dict) -> tuple[bool, str]:
        from resources.models import Course

        course_url = (
            item_data.get("course_url") or item_data.get("access_link") or ""
        ).strip()
        if course_url:
            existing = Course.objects.filter(access_link__iexact=course_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "course access_link exact match"

        incoming_title = item_data.get("title_en") or item_data.get("title") or ""
        incoming_instructor = self._normalize_text(item_data.get("instructor") or "")
        if not incoming_instructor:
            incoming_instructor = self._extract_instructor(
                item_data.get("description_en") or ""
            )

        if incoming_title and incoming_instructor:
            incoming_pair = (
                f"{self._normalize_text(incoming_title)} {incoming_instructor}"
            )
            for course in Course.objects.only(
                "id", "title", "title_en", "description", "description_en"
            ):
                existing_title = course.title_en or course.title
                existing_instructor = self._extract_instructor(
                    course.description_en or course.description
                )
                if not existing_instructor:
                    continue
                existing_pair = (
                    f"{self._normalize_text(existing_title)} {existing_instructor}"
                )
                if SequenceMatcher(None, incoming_pair, existing_pair).ratio() >= 0.85:
                    self._set_duplicate_match(course)
                    return True, "course (title + instructor) similarity >= 85%"

        if incoming_title:
            for course in Course.objects.only("id", "title", "title_en"):
                existing_title = course.title_en or course.title
                if self._title_similarity(incoming_title, existing_title) >= 0.90:
                    self._set_duplicate_match(course)
                    return True, "course title similarity >= 90%"

        return False, ""

    def _dedup_institution(self, item_data: dict) -> tuple[bool, str]:
        from institutions.models import Institution

        ror_id = (item_data.get("ror_id") or "").strip()
        if ror_id:
            existing = Institution.objects.filter(ror_id__iexact=ror_id).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "institution ror_id exact match"

        website_url = self._normalize_url(
            item_data.get("website_url") or item_data.get("website"), strip_www=True
        )
        if website_url:
            for institution in Institution.objects.only("id", "website"):
                if (
                    self._normalize_url(institution.website, strip_www=True)
                    == website_url
                ):
                    self._set_duplicate_match(institution)
                    return True, "institution normalized website_url exact match"

        incoming_name = item_data.get("name_en") or item_data.get("name") or ""
        if incoming_name:
            for institution in Institution.objects.only("id", "name", "name_en"):
                existing_name = institution.name_en or institution.name
                if self._title_similarity(incoming_name, existing_name) >= 0.90:
                    self._set_duplicate_match(institution)
                    return True, "institution name similarity >= 90%"

        return False, ""

    def _check_duplicate_policy(self, category, item_data) -> tuple[bool, str]:
        self._last_duplicate_match_id = ""

        deterministic_checks = {
            "events": self._dedup_event,
            "tools": self._dedup_tool,
            "news": self._dedup_news,
            "courses": self._dedup_course,
            "institutions": self._dedup_institution,
        }

        check_fn = deterministic_checks.get(category)
        if check_fn:
            is_dup, reason = check_fn(item_data)
            if is_dup:
                self._record_duplicate_skip(category, item_data, reason)
                return True, reason

        semantic_title = (
            item_data.get("title_en")
            or item_data.get("title")
            or item_data.get("name_en")
            or item_data.get("name")
            or ""
        )
        if semantic_title:
            try:
                from scraping.embeddings import find_semantic_duplicate

                duplicate_meta = find_semantic_duplicate(
                    semantic_title, category, threshold=0.88
                )
                if duplicate_meta is not None:
                    self._last_duplicate_match_id = str(
                        getattr(duplicate_meta, "item_id", "") or duplicate_meta.id
                    )
                    reason = "semantic fallback similarity >= 88%"
                    self._record_duplicate_skip(category, item_data, reason)
                    return True, reason
            except Exception as exc:
                self._log_error("semantic_dedup", str(exc), source=semantic_title)

        return False, ""

    def is_duplicate(self, title, category, model_class):
        """
        Two-step duplicate detection:
        Step 1: Exact match check (fast, O(1))
        Step 2: Semantic similarity check (slower, embedding-based)
        Returns True if duplicate found, False if new item.
        """
        item_data = {"title_en": title, "title": title}
        is_dup, _ = self._check_duplicate_policy(category, item_data)
        return is_dup

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
                        "rate_limited",
                        f"429 from {url}",
                        source=source_name,
                        url=url,
                        extra={"attempt": attempt, "sleep": sleep},
                    )
                    time.sleep(sleep)
                    continue

                if response.status_code >= 500:
                    sleep = min(
                        self.BACKOFF_BASE * (2 ** (attempt - 1)),
                        self.BACKOFF_MAX,
                    )
                    self._log_error(
                        "server_error",
                        f"{response.status_code} from {url}",
                        source=source_name,
                        url=url,
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
                    self.BACKOFF_BASE * (2 ** (attempt - 1)),
                    self.BACKOFF_MAX,
                )
                self._log_error(
                    "connection_error",
                    str(exc),
                    source=source_name,
                    url=url,
                    extra={"attempt": attempt, "sleep": sleep},
                )
                time.sleep(sleep)

            except requests.Timeout as exc:
                elapsed = time.monotonic() - t0
                last_exc = exc
                sleep = min(
                    self.BACKOFF_BASE * (2 ** (attempt - 1)),
                    self.BACKOFF_MAX,
                )
                self._log_error(
                    "timeout",
                    str(exc),
                    source=source_name,
                    url=url,
                    extra={"attempt": attempt, "timeout": timeout, "sleep": sleep},
                )
                time.sleep(sleep)

            except requests.RequestException as exc:
                last_exc = exc
                self._log_error(
                    "request_error",
                    str(exc),
                    source=source_name,
                    url=url,
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

    def _get_health(
        self, source_name: str, base_url: str = ""
    ) -> "ScrapingSourceHealth":
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
        self,
        source_name: str,
        base_url: str = "",
        response_time: float | None = None,
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
            self.category,
            error_type,
            message,
            source or self.name,
            url,
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

    def clean_text(self, text: str) -> str:
        """Remove excessive whitespace from text.

        If the text contains a significant proportion of Arabic characters
        (> 10 %), Arabic-specific normalization is applied first.
        """
        if not text:
            return ""

        text = re.sub(r"\s+", " ", text).strip()

        if self.detect_arabic_ratio(text) > 0.1:
            text = self.normalize_arabic_text(text)
        return text

    # ------------------------------------------------------------------
    # Arabic text normalization
    # ------------------------------------------------------------------

    def normalize_arabic_text(self, text):
        """Normalize Arabic text for consistent storage and comparison.

        Steps:
        1. Strip tashkeel (diacritics).
        2. Normalize alef variants (أ إ آ) → bare alef (ا).
        3. Normalize teh marbuta (ة) → heh (ه).
        4. Strip extra whitespace.
        """
        if not text or len(text.strip()) == 0:
            return text
        try:
            import pyarabic.araby as araby

            text = araby.strip_tashkeel(text)
            text = araby.normalize_alef(text)
            text = araby.normalize_lamalef(text)
        except ImportError:
            import re

            # Manual fallback if pyarabic not available
            # Remove diacritics
            text = re.sub(r"[\u0617-\u061A\u064B-\u065F]", "", text)
            # Normalize alef variants
            text = re.sub(r"[أإآ]", "ا", text)
            # Normalize teh marbuta
            text = re.sub(r"ة", "ه", text)
        return text.strip()

    def detect_arabic_ratio(self, text):
        """
        Returns ratio of Arabic characters to total
        alphabetic characters. Returns 0.0 if empty.
        """
        if not text or len(text.strip()) == 0:
            return 0.0
        import re

        arabic_chars = len(
            re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text)
        )
        alpha_chars = len(re.findall(r"[^\W\d_]", text))
        if alpha_chars == 0:
            return 0.0
        return arabic_chars / alpha_chars

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------

    def detect_language(self, text):
        """
        Detect the language of a text string.
        Returns ISO language code: 'ar', 'fr', 'en', 'unknown'
        Uses langdetect library with deterministic seed.
        """
        if not text or len(text.strip()) < 20:
            return "unknown"

        # First check Arabic using Unicode ratio (faster)
        if self.detect_arabic_ratio(text) >= 0.30:
            return "ar"

        try:
            from langdetect import detect, DetectorFactory
            from langdetect.lang_detect_exception import LangDetectException

            DetectorFactory.seed = 0  # deterministic
            lang = detect(text)
            # Only return languages we support
            if lang in ["ar", "fr", "en"]:
                return lang
            return "unknown"
        except Exception:
            return "unknown"

    def is_relevant_language(self, text):
        """
        Returns True if text is in Arabic, French, or English.
        Returns True for unknown (give benefit of doubt).
        Returns False for clearly irrelevant languages
        like Chinese, Japanese, Korean, etc.
        """
        lang = self.detect_language(text)
        return lang in ["ar", "fr", "en", "unknown"]

    def is_event_date_valid(self, date_value, max_days_past=30, max_days_future=730):
        if date_value is None:
            return True
        from django.utils import timezone
        import datetime

        now = timezone.now()
        try:
            if isinstance(date_value, str):
                event_date = self.parse_date(date_value)
                if not event_date:
                    return True
            else:
                event_date = date_value
            if not hasattr(event_date, "tzinfo"):
                return True
            if event_date.tzinfo is None:
                import pytz

                event_date = pytz.utc.localize(event_date)
            past_limit = now - datetime.timedelta(days=max_days_past)
            future_limit = now + datetime.timedelta(days=max_days_future)
            return past_limit <= event_date <= future_limit
        except Exception:
            return True

    def validate_required_fields(self, item, category):
        REQUIRED = {
            "events": [
                ("title_en", 5),
                ("description_en", 20),
            ],
            "tools": [
                ("title_en", 3),
                ("description_en", 20),
                ("access_link", 5),
            ],
            "news": [
                ("title_en", 10),
                ("content_en", 50),
            ],
            "courses": [
                ("title_en", 5),
                ("description_en", 30),
            ],
            "institutions": [
                ("name_en", 3),
            ],
        }
        required = REQUIRED.get(category, [])
        missing = []
        for field_key, min_len in required:
            value = item.get(field_key, "")
            if not value or len(str(value).strip()) < min_len:
                missing.append(field_key)
        return len(missing) == 0, missing

    def auto_fill_missing_fields(self, item, category):
        """
        Try to auto-fill missing Arabic fields using LLM
        if title_en exists but title_ar is missing.
        Returns updated item dict.
        """
        title_en = str(item.get("title_en", "")).strip()
        desc_en = str(item.get("description_en", "")).strip()

        if not title_en:
            return item

        needs_arabic_title = not str(item.get("title_ar", "")).strip()
        needs_arabic_desc = not str(item.get("description_ar", "")).strip() and desc_en

        if needs_arabic_title or needs_arabic_desc:
            try:
                from scraping.llm_validation import GroqLLMClient

                client = GroqLLMClient()

                prompt = f"""
Translate these fields to Arabic. Return ONLY JSON, no other text.
{{
  "title_ar": "Arabic translation of: {title_en}",
  "description_ar": "Arabic translation of: {desc_en[:300]}"
}}
"""
                response = client._chat(prompt)
                import json
                import re

                match = re.search(r"\{.*?\}", response, re.DOTALL)
                if match:
                    translations = json.loads(match.group())
                    if needs_arabic_title:
                        item["title_ar"] = translations.get("title_ar", title_en)
                    if needs_arabic_desc:
                        item["description_ar"] = translations.get(
                            "description_ar", desc_en
                        )
            except Exception:
                if needs_arabic_title:
                    item["title_ar"] = title_en
                if needs_arabic_desc:
                    item["description_ar"] = desc_en

        return item

    def validate_and_prepare(self, item, category):
        """
        Run all validations. Returns (is_valid, item, reason)
        Call this before saving any scraped item.
        """
        if not hasattr(self, "validation_stats"):
            self.validation_stats = {
                "passed": 0,
                "failed_date": 0,
                "failed_fields": 0,
                "failed_freshness": 0,
            }

        if category == "events":
            start_date = item.get("start_date") or item.get("date")
            if not self.is_event_date_valid(start_date):
                self.validation_stats["failed_date"] += 1
                return False, item, "past_or_invalid_date"

        if category == "news":
            if not self.is_content_fresh(item, "news"):
                self.validation_stats["failed_freshness"] += 1
                return False, item, "content_too_old"

        is_valid, missing = self.validate_required_fields(item, category)
        if not is_valid:
            self.validation_stats["failed_fields"] += 1
            return False, item, f"missing_fields:{missing}"

        self.validation_stats["passed"] += 1
        return True, item, None

    # ------------------------------------------------------------------
    # Freshness filtering
    # ------------------------------------------------------------------

    def is_event_still_valid(self, event_date, grace_days=7):
        """
        Returns True if event is in the future or within grace_days of today.
        Returns False if event has passed.
        Returns True if date is None (unknown = keep it).
        """
        if event_date is None:
            return True
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now().date()
        if hasattr(event_date, "date"):
            event_date = event_date.date()
        cutoff = now - timedelta(days=grace_days)
        return event_date >= cutoff

    def is_news_fresh(self, published_date, max_age_days=365):
        """
        Returns True if news/paper was published within max_age_days.
        Default: reject papers older than 1 year.
        Returns True if date is None.
        """
        if published_date is None:
            return True
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now().date()
        if hasattr(published_date, "date"):
            published_date = published_date.date()
        cutoff = now - timedelta(days=max_age_days)
        return published_date >= cutoff

    def is_content_fresh(self, item, category, max_age_days=None):
        DEFAULT_MAX_AGE = {
            "news": 365,
            "events": 30,
            "tools": None,
            "courses": None,
            "institutions": None,
        }
        if max_age_days is None:
            max_age_days = DEFAULT_MAX_AGE.get(category)
        if max_age_days is None:
            return True
        from django.utils import timezone
        import datetime

        date_fields = [
            "published_date",
            "publication_date",
            "date",
            "start_date",
            "created_at",
        ]
        item_date = None
        for field in date_fields:
            val = item.get(field)
            if val:
                item_date = self.parse_date(str(val))
                if item_date:
                    break
        if not item_date:
            return True
        now = timezone.now()
        if hasattr(item_date, "tzinfo"):
            if item_date.tzinfo is None:
                import pytz

                item_date = pytz.utc.localize(item_date)
        age_days = (now - item_date).days
        return age_days <= max_age_days

    def is_course_still_available(
        self, end_date=None, last_updated=None, max_age_days=730
    ):
        """
        Returns True if course has no end date (self-paced) or end date is
        in future. Also checks if content is not too old (2 years).
        """
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now().date()

        if end_date is not None:
            if hasattr(end_date, "date"):
                end_date = end_date.date()
            if end_date < now:
                return False

        if last_updated is not None:
            if hasattr(last_updated, "date"):
                last_updated = last_updated.date()
            cutoff = now - timedelta(days=max_age_days)
            if last_updated < cutoff:
                return False

        return True

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
            from scraping.field_mapping import calculate_completeness_score
            from scraping.models import ScrapedItemMeta
        except Exception as exc:
            logger.debug("Intelligence module not available: %s", exc)
            return {"status": "skipped", "reason": str(exc)}

        scored = 0
        domain_counts: dict[str, int] = {}
        lang_counts: dict[str, int] = {}
        avg_score = 0.0

        for item in self.results:
            title = item.get("title", "")
            if not title:
                continue

            # Build text for classification
            text = f"{title} {item.get('description', '')} {item.get('type', '')}"

            # Language detection
            detected_lang = self.detect_language(
                item.get("title_en", "") + " " + item.get("description_en", "")
            )
            logger.debug(
                "Language detected for '%s': %s",
                title[:60],
                detected_lang,
            )

            # Classify
            domain_scores = classify_domain(text)
            primary_domain = classify_domain_primary(text)

            # Score
            score = compute_relevance_score(
                text=text,
                has_description=bool(item.get("description") or item.get("type")),
                has_website=bool(item.get("url")),
                has_arabic=any(ord(c) > 0x0600 and ord(c) < 0x06FF for c in text),
                domain_scores=domain_scores,
            )

            completeness = calculate_completeness_score(item, self.category)

            # Store metadata
            defaults = {
                "domain_scores": domain_scores,
                "primary_domain": primary_domain,
                "relevance_score": score,
                "completeness_score": completeness,
            }
            # Persist language if the model supports it
            if hasattr(ScrapedItemMeta, "language"):
                defaults["language"] = detected_lang
            else:
                logger.debug("ScrapedItemMeta has no language field for '%s'", title)

            try:
                item_title = item.get("title_en", "") or title
                meta_record, _ = ScrapedItemMeta.objects.update_or_create(
                    category=self.category,
                    item_title=item_title[:300],
                    defaults=defaults,
                )
            except Exception:
                meta_record = None  # Non-critical — don't fail the scrape

            # Compute and persist title embedding for semantic duplicate detection
            if meta_record is not None:
                try:
                    from scraping.embeddings import get_embedding

                    embedding = get_embedding(item.get("title_en", ""))
                    if embedding:
                        meta_record.title_embedding = embedding
                        meta_record.save(update_fields=["title_embedding"])
                except MemoryError as e:
                    self._log_error(
                        "embedding_oom",
                        "Not enough RAM for embedding generation. "
                        "Consider reducing batch size.",
                        source=item.get("title_en", ""),
                    )
                except Exception as e:
                    self._log_error(
                        "embedding_failed",
                        f"Embedding generation failed: {str(e)}. "
                        f"Semantic deduplication disabled for this item.",
                        source=item.get("title_en", ""),
                    )

            scored += 1
            avg_score += score
            domain_counts[primary_domain] = domain_counts.get(primary_domain, 0) + 1
            lang_counts[detected_lang] = lang_counts.get(detected_lang, 0) + 1

        avg_score = round(avg_score / max(scored, 1), 1)

        summary = {
            "status": "completed",
            "items_scored": scored,
            "avg_relevance_score": avg_score,
            "domain_distribution": domain_counts,
            "language_distribution": lang_counts,
        }
        logger.info(
            "intelligence_scored",
            extra={
                "category": self.category,
                "source_name": self.name,
                "items_scored": scored,
                "avg_relevance_score": avg_score,
                "domain_distribution": domain_counts,
                "language_distribution": lang_counts,
            },
        )
        return summary
