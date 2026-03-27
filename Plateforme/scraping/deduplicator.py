from __future__ import annotations

from scraping.base_scraper import StandardEvent


class EventDeduplicator:
    """Deduplicate using title + date and URL fallback."""

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join((value or "").lower().split())

    def deduplicate(
        self, events: list[StandardEvent]
    ) -> tuple[list[StandardEvent], int]:
        unique: list[StandardEvent] = []
        seen: set[tuple[str, str, str]] = set()
        duplicates = 0

        for event in events:
            key = (
                self._norm(event.title),
                event.start_date.date().isoformat(),
                self._norm(event.url),
            )
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            unique.append(event)

        return unique, duplicates
