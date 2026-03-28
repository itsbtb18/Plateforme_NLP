"""Wayback Machine fallback support for unreachable sources."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

WAYBACK_API_URL = "https://archive.org/wayback/available"
WAYBACK_CDX_URL = "http://web.archive.org/cdx/search/cdx"


class MockResponse:
    """Mimics requests.Response for Wayback-sourced content."""

    def __init__(
        self,
        html: str,
        url: str,
        *,
        source: str = "wayback",
        archived_snapshot_url: str = "",
    ):
        self.text = html
        self.content = html.encode("utf-8")
        self.status_code = 200
        self.url = url
        self.source = source
        self.archived_snapshot_url = archived_snapshot_url
        self.headers = {"content-type": "text/html; charset=utf-8"}

    def raise_for_status(self) -> None:
        return None


class WaybackMachineFallback:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "PlateformeNLP-Scraper/1.0"

    def get_latest_snapshot(
        self,
        url: str,
        max_age_days: int = 90,
    ) -> MockResponse | None:
        """Fetch the most recent Wayback snapshot and return a response-like object."""
        snapshot_url = self._find_best_snapshot(url, max_age_days)
        if not snapshot_url:
            logger.info(
                "[Wayback] No snapshot found for %s within %s days",
                url,
                max_age_days,
            )
            return None

        try:
            response = self.session.get(snapshot_url, timeout=(5, 15))
            if response.status_code == 200:
                cleaned_html = self.strip_wayback_toolbar(response.text)
                logger.info("[Wayback] Retrieved snapshot: %s", snapshot_url)
                return MockResponse(
                    cleaned_html,
                    url,
                    source="wayback",
                    archived_snapshot_url=snapshot_url,
                )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "[Wayback] Failed to fetch snapshot %s: %s",
                snapshot_url,
                exc,
            )

        return None

    def _find_best_snapshot(self, url: str, max_age_days: int) -> str | None:
        """Use CDX API to find most recent successful snapshot."""
        from_timestamp = (datetime.now() - timedelta(days=max_age_days)).strftime(
            "%Y%m%d"
        )

        params = {
            "url": url,
            "output": "json",
            "fl": "timestamp,statuscode,original",
            "filter": "statuscode:200",
            "from": from_timestamp,
            "limit": "1",
            "sort": "reverse",
        }

        try:
            response = self.session.get(WAYBACK_CDX_URL, params=params, timeout=(5, 10))
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            timestamp = data[1][0]
            original_url = data[1][2]
            return f"https://web.archive.org/web/{timestamp}/{original_url}"

        except (requests.exceptions.RequestException, ValueError, IndexError) as exc:
            logger.warning("[Wayback] CDX lookup failed for %s: %s", url, exc)
            return None

    def strip_wayback_toolbar(self, html: str) -> str:
        """Remove Wayback Machine toolbar/noise from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(id=["wm-ipp-base", "wm-ipp", "donato", "wm-toolbar"]):
            tag.decompose()

        for script in soup.find_all("script", src=True):
            if "archive.org" in str(script.get("src", "")):
                script.decompose()

        return str(soup)
