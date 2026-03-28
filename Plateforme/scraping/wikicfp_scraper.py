from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin

from scraping.base_scraper import BaseEventScraper, StandardEvent

logger = logging.getLogger(__name__)


class WikiCFPScraper(BaseEventScraper):
    source_name = "WikiCFP"
    base_url = "https://www.wikicfp.com"

    def scrape(self) -> list[StandardEvent]:
        events: list[StandardEvent] = []

        html = self.fetch_url(f"{self.base_url}/cfp/")
        soup = self.parse_html(html)

        rows = soup.select("table.gglu tr")
        for row in rows:
            anchor = row.select_one("a[href*='event.showcfp']")
            if not anchor:
                continue

            title = anchor.get_text(" ", strip=True)
            url = urljoin(self.base_url, anchor.get("href", ""))
            raw_text = row.get_text(" ", strip=True)

            start_date = self._extract_first_date(raw_text)
            if start_date is None:
                continue

            event = StandardEvent(
                title=title,
                description=raw_text,
                location=self._guess_location(raw_text),
                start_date=start_date,
                end_date=None,
                deadline=self._extract_deadline(raw_text),
                source=self.source_name,
                url=url,
            )
            events.append(event)

        logger.info("[SCRAPER] %s -> %s events found", self.source_name, len(events))
        return events

    def _extract_first_date(self, text: str) -> datetime | None:
        tokens = text.replace("-", " ").split()
        for i in range(max(0, len(tokens) - 2)):
            candidate = " ".join(tokens[i : i + 3])
            dt = self.parse_datetime(candidate)
            if dt is not None:
                return dt
        return None

    def _extract_deadline(self, text: str) -> datetime | None:
        lowered = text.lower()
        if "deadline" not in lowered and "cfp" not in lowered:
            return None
        return self._extract_first_date(text)

    @staticmethod
    def _guess_location(text: str) -> str:
        for marker in ["USA", "UK", "France", "Germany", "Algeria", "Online"]:
            if marker.lower() in text.lower():
                return marker
        return "Unknown"
