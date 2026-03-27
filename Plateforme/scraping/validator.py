from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from scraping.base_scraper import StandardEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationResult:
    event: StandardEvent
    is_valid: bool
    reason: str = ""


class EventValidator:
    """Strict validation for normalized events."""

    @staticmethod
    def _is_empty(value: str) -> bool:
        return not bool((value or "").strip())

    def validate(self, event: StandardEvent) -> ValidationResult:
        if self._is_empty(event.title):
            return ValidationResult(event=event, is_valid=False, reason="empty_title")

        if self._is_empty(event.url):
            return ValidationResult(event=event, is_valid=False, reason="missing_url")

        if not isinstance(event.start_date, datetime):
            return ValidationResult(
                event=event,
                is_valid=False,
                reason="invalid_start_date",
            )

        if event.end_date is not None and event.end_date < event.start_date:
            return ValidationResult(
                event=event,
                is_valid=False,
                reason="end_before_start",
            )

        if event.deadline is not None and event.deadline > event.start_date:
            return ValidationResult(
                event=event,
                is_valid=False,
                reason="deadline_after_start",
            )

        return ValidationResult(event=event, is_valid=True, reason="ok")

    def validate_many(
        self, events: list[StandardEvent]
    ) -> tuple[list[StandardEvent], list[ValidationResult]]:
        valid: list[StandardEvent] = []
        invalid: list[ValidationResult] = []

        for event in events:
            result = self.validate(event)
            if result.is_valid:
                valid.append(event)
            else:
                invalid.append(result)
                logger.info(
                    "[VALIDATION] rejected source=%s title=%s reason=%s",
                    event.source,
                    event.title,
                    result.reason,
                )

        logger.info("[VALIDATION] %s valid, %s invalid", len(valid), len(invalid))
        return valid, invalid
