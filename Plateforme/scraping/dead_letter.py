import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEAD_LETTER_DIR = Path("logs/scraping_dead_letters")


def record_dead_letter(
    category: str,
    source_name: str,
    item: dict,
    error: str,
    retry_count: int,
) -> None:
    """
    Persists a permanently failed scrape item for manual review.
    """
    try:
        DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = DEAD_LETTER_DIR / f"{category}_{timestamp}.jsonl"

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "category": category,
            "source": source_name,
            "retry_count": retry_count,
            "error": error,
            "item_url": item.get("url", "unknown"),
            "item_title": item.get("title", "unknown"),
        }

        with open(filename, "a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.warning(
            "item_dead_lettered",
            extra={
                "category": category,
                "source": source_name,
                "url": record["item_url"],
            },
        )
    except Exception as exc:
        logger.error("dead_letter_write_failed", extra={"error": str(exc)})
