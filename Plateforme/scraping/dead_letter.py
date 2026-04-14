import json
import logging
from datetime import UTC, datetime

from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)

DEAD_LETTER_DIR = SS.DEAD_LETTER_DIR


def _validate_dead_letter_dir() -> bool:
    try:
        DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
        test_file = DEAD_LETTER_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        logger.info("Dead letter directory ready: %s", DEAD_LETTER_DIR)
        return True
    except Exception as exc:
        logger.error("CRITICAL: Dead letter directory not writable: %s", exc)
        return False


DEAD_LETTER_DIR_READY = _validate_dead_letter_dir()


def record_dead_letter(
    category: str,
    url: str,
    reason: str,
    data: dict | None = None,
    *legacy_args,
) -> bool:
    """
    Persists a permanently failed scrape item for manual review.
    """

    # Backward compatibility for old call shape:
    # record_dead_letter(category, source_name, item, error, retry_count)
    if isinstance(reason, dict):
        source_name = str(url)
        item = reason
        error = str(data or "")
        retry_count = int(legacy_args[0]) if legacy_args else 0
        url = str(item.get("url", "unknown"))
        reason = error or "unknown_error"
        data = {
            "source": source_name,
            "retry_count": retry_count,
            "item_title": item.get("title", "unknown"),
            "item": item,
        }

    if not DEAD_LETTER_DIR_READY:
        logger.error(
            "dead_letter_LOST: category=%s url=%s reason=%s - directory not ready",
            category,
            url,
            reason,
        )
        return False

    try:
        filename = f"{category}_{datetime.now(UTC).strftime('%Y%m%d')}.jsonl"

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "category": category,
            "url": url,
            "reason": reason,
            "data": data or {},
        }

        dead_file = DEAD_LETTER_DIR / filename
        with open(dead_file, "a", encoding="utf-8") as file_handle:
            file_handle.write(
                json.dumps(record, default=str, ensure_ascii=False) + "\n"
            )

        logger.warning(
            "item_dead_lettered",
            extra={
                "category": category,
                "url": url,
                "reason": reason,
            },
        )
        return True
    except Exception as exc:
        logger.error(
            "dead_letter_write_failed: %s | url=%s | category=%s | reason=%s",
            exc,
            url,
            category,
            reason,
        )
        return False


def record(url: str, reason: str, timestamp: str) -> None:
    """Store unreachable site event in dead-letter log format."""
    record_dead_letter(
        category="sites",
        url=url,
        reason=reason,
        data={
            "timestamp": timestamp,
            "kind": "site_unreachable",
        },
    )
