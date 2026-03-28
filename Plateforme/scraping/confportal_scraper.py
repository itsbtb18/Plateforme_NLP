from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin

from scraping.base_scraper import BaseEventScraper, StandardEvent

logger = logging.getLogger(__name__)


class ConfPortalScraper(BaseEventScraper):
    """Example scraper for conference listing portals with card-style HTML."""

    source_name = "ConfPortal"
    base_url = "https://confportal.com"

    def scrape(self) -> list[StandardEvent]:
        events: list[StandardEvent] = []

        html = self.fetch_url(f"{self.base_url}/conferences")
        soup = self.parse_html(html)

        cards = soup.select("article, .event-card, .conference-card")
        for card in cards:
            anchor = card.select_one("a[href]")
            title_node = card.select_one("h2, h3, .title")
            if not anchor or not title_node:
                continue

            title = title_node.get_text(" ", strip=True)
            url = urljoin(self.base_url, anchor.get("href", ""))
            description = card.get_text(" ", strip=True)
            location = self._extract_location(card)
            start_date = self._extract_date_from_card(card)

            if start_date is None:
                continue

            events.append(
                StandardEvent(
                    title=title,
                    description=description,
                    location=location,
                    start_date=start_date,
                    end_date=None,
                    deadline=self._extract_deadline_from_card(card),
                    source=self.source_name,
                    url=url,
                )
            )

        logger.info("[SCRAPER] %s -> %s events found", self.source_name, len(events))
        return events

    def _extract_date_from_card(self, card) -> datetime | None:
        date_node = card.select_one("time[datetime], .date, .event-date")
        if not date_node:
            return None

        raw = date_node.get("datetime") if date_node.has_attr("datetime") else ""
        raw = raw or date_node.get_text(" ", strip=True)
        return self.parse_datetime(raw)

    def _extract_deadline_from_card(self, card) -> datetime | None:
        deadline_node = card.find(string=lambda s: s and "deadline" in s.lower())
        if not deadline_node:
            return None
        return self.parse_datetime(str(deadline_node))

    @staticmethod
    def _extract_location(card) -> str:
        location_node = card.select_one(".location, .venue")
        if location_node:
            return location_node.get_text(" ", strip=True)
        return "Unknown"
