import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from django.core.cache import cache

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = Path("logs/scraping_checkpoints")
CHECKPOINT_TTL = 86400 * 3  # 3 days in seconds


class ScraperCheckpoint:
    """
    Saves and restores scraper progress so runs can resume
    after crashes without restarting from scratch.

    Usage:
        cp = ScraperCheckpoint("courses", run_id)

        # Check if we have a saved position
        start_from = cp.get("page_cursor", default=0)

        for page in range(start_from, total_pages):
            process_page(page)
            cp.set("page_cursor", page + 1)
            cp.set("items_processed", cp.get("items_processed", 0) + page_size)

        cp.clear()  # Done - remove checkpoint
    """

    def __init__(self, category: str, run_id: str):
        """Initialize a checkpoint state container for one scraper run.

        Args:
            category: Scraper category key (for example: courses, tools).
            run_id: Unique run identifier used to scope checkpoint state.
        """
        self.category = category
        self.run_id = str(run_id)
        self.cache_key = f"checkpoint:{category}:{self.run_id}"
        self._data: dict = {}
        self._load()

    @property
    def _file_path(self) -> Path:
        token = hashlib.sha256(self.cache_key.encode("utf-8")).hexdigest()[:16]
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        return CHECKPOINT_DIR / f"{self.category}_{token}.json"

    def _load(self) -> None:
        try:
            raw = cache.get(self.cache_key)
            if raw:
                self._data = json.loads(raw)
                logger.info(
                    "checkpoint_loaded",
                    extra={
                        "category": self.category,
                        "run_id": self.run_id,
                        "keys": list(self._data.keys()),
                    },
                )
                return
        except Exception as exc:
            logger.warning(
                "checkpoint_load_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )

        self._load_from_file()

    def _load_from_file(self) -> None:
        try:
            path = self._file_path
            if not path.exists():
                self._data = {}
                return
            self._data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(
                "checkpoint_loaded_from_file",
                extra={
                    "category": self.category,
                    "run_id": self.run_id,
                    "path": str(path),
                },
            )
        except Exception as exc:
            logger.warning(
                "checkpoint_file_load_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )
            self._data = {}

    def get(self, key: str, default: object | None = None) -> object | None:
        """Read a checkpoint value.

        Args:
            key: Data key to fetch.
            default: Fallback when key is absent.

        Returns:
            object | None: Stored value or fallback default.
        """
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        """Write one checkpoint value and persist immediately.

        Args:
            key: Data key to write.
            value: Serializable value to store.
        """
        self._data[key] = value
        self._save()

    def set_many(self, updates: dict[str, object]) -> None:
        """Write multiple checkpoint values atomically.

        Args:
            updates: Mapping of keys to values.
        """
        self._data.update(updates)
        self._save()

    def has(self, key: str) -> bool:
        """Return whether a checkpoint key exists.

        Args:
            key: Data key to check.

        Returns:
            bool: ``True`` when key exists in current state.
        """
        return key in self._data

    def is_resuming(self) -> bool:
        """Return whether this run has existing checkpoint data.

        Returns:
            bool: ``True`` when at least one checkpoint value exists.
        """
        return bool(self._data)

    def _save(self) -> None:
        self._data["_updated_at"] = datetime.now(UTC).isoformat()
        payload = json.dumps(self._data)

        try:
            cache.set(
                self.cache_key,
                payload,
                timeout=CHECKPOINT_TTL,
            )
        except Exception as exc:
            logger.warning(
                "checkpoint_save_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )

        self._save_to_file(payload)

    def _save_to_file(self, payload: str) -> None:
        try:
            self._file_path.write_text(payload, encoding="utf-8")
        except Exception as exc:
            logger.warning(
                "checkpoint_file_save_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )

    def clear(self) -> None:
        """Delete cache/file checkpoint state for this run.

        Raises:
            Exception: Cache and file delete errors are logged and suppressed.
        """
        try:
            cache.delete(self.cache_key)
        except Exception as exc:
            logger.warning(
                "checkpoint_clear_failed",
                extra={"error": str(exc)},
            )

        try:
            path = self._file_path
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning(
                "checkpoint_file_clear_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )

        self._data = {}
        logger.info(
            "checkpoint_cleared",
            extra={
                "category": self.category,
                "run_id": self.run_id,
            },
        )

    def mark_source_done(self, source_name: str) -> None:
        """Mark a logical source step as completed for resume skip logic.

        Args:
            source_name: Stable source step identifier.
        """
        done = self.get("completed_sources", [])
        if source_name not in done:
            done.append(source_name)
            self.set("completed_sources", done)

    def is_source_done(self, source_name: str) -> bool:
        """Check whether a source step is already completed.

        Args:
            source_name: Stable source step identifier.

        Returns:
            bool: ``True`` if source was previously marked done.
        """
        return source_name in self.get("completed_sources", [])

    def get_summary(self) -> dict[str, object | list[str] | int | bool | None]:
        """Return an operational summary snapshot for logs and diagnostics.

        Returns:
            dict[str, object | list[str] | int | bool | None]: Summary payload.
        """
        return {
            "category": self.category,
            "run_id": self.run_id,
            "is_resuming": self.is_resuming(),
            "completed_sources": self.get("completed_sources", []),
            "items_processed": self.get("items_processed", 0),
            "last_updated": self.get("_updated_at"),
        }
