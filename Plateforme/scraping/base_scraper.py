from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class StandardEvent:
    title: str
    description: str
    location: str
    start_date: datetime
    end_date: datetime | None
    deadline: datetime | None
    source: str
    url: str


class BaseEventScraper(ABC):
    """Base scraper with robust HTTP behavior and standard event shape helpers."""

    source_name: str = "unknown"
    base_url: str = ""

    def __init__(
        self,
        timeout_seconds: int = 10,
        max_retries: int = 3,
        backoff_factor: float = 0.6,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout_seconds = int(timeout_seconds)
        self.max_retries = int(max_retries)
        self.backoff_factor = float(backoff_factor)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        retry = Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_url(self, url: str) -> str:
        """Fetch URL with retry/backoff and strict HTTP error handling."""
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("[SCRAPER] %s -> HTTP ERROR (%s)", self.source_name, status)
            raise
        except requests.exceptions.RequestException:
            logger.warning("[SCRAPER] %s -> FAILED (request error)", self.source_name)
            raise

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html or "", "html.parser")

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None

        value = value.strip()
        candidates = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for pattern in candidates:
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
        return None

    @staticmethod
    def to_standard_event(payload: dict[str, Any]) -> StandardEvent | None:
        try:
            title = str(payload.get("title", "")).strip()
            description = str(payload.get("description", "")).strip()
            location = str(payload.get("location", "")).strip()
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            deadline = payload.get("deadline")
            source = str(payload.get("source", "")).strip()
            url = str(payload.get("url", "")).strip()

            if not isinstance(start_date, datetime):
                return None
            if end_date is not None and not isinstance(end_date, datetime):
                return None
            if deadline is not None and not isinstance(deadline, datetime):
                return None

            return StandardEvent(
                title=title,
                description=description,
                location=location,
                start_date=start_date,
                end_date=end_date,
                deadline=deadline,
                source=source,
                url=url,
            )
        except Exception:
            return None

    @abstractmethod
    def scrape(self) -> list[StandardEvent]:
        """Return standardized events from this source."""
