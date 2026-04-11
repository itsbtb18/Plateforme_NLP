import hashlib
import json
import logging
from datetime import UTC, datetime

from django.core.cache import cache

from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = SS.CHECKPOINT_DIR
CHECKPOINT_TTL = SS.CHECKPOINT_TTL


def _validate_checkpoint_dir() -> bool:
    try:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        test_file = CHECKPOINT_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        logger.info("Checkpoint directory ready: %s", CHECKPOINT_DIR)
        return True
    except Exception as exc:
        logger.error("CRITICAL: Checkpoint directory not writable: %s", exc)
        logger.error("Resume safety is DISABLED - runs cannot be resumed")
        return False


CHECKPOINT_DIR_READY = _validate_checkpoint_dir()


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
        self.load()

    @property
    def _file_path(self):
        token = hashlib.sha256(self.cache_key.encode("utf-8")).hexdigest()[:16]
        return CHECKPOINT_DIR / f"{self.category}_{token}.json"

    def load(self):
        if not CHECKPOINT_DIR_READY:
            logger.warning("Checkpoint load skipped - directory not ready")
            self._data = {}
            return None

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
                return self._data
        except Exception as exc:
            logger.warning(
                "checkpoint_load_failed",
                extra={"error": str(exc), "run_id": self.run_id},
            )

        try:
            path = self._file_path
            if not path.exists():
                self._data = {}
                return None
            self._data = json.loads(path.read_text(encoding="utf-8") or "{}")
            logger.info(
                "checkpoint_loaded_from_file",
                extra={
                    "category": self.category,
                    "run_id": self.run_id,
                    "path": str(path),
                },
            )
            return self._data
        except Exception as exc:
            logger.error("checkpoint_file_load_failed: %s", exc)
            self._data = {}
            return None

    def save(self, data: dict) -> bool:
        if not CHECKPOINT_DIR_READY:
            logger.warning("Checkpoint save skipped - directory not ready")
            return False

        try:
            payload_data = dict(data)
            payload_data["_updated_at"] = datetime.now(UTC).isoformat()
            payload = json.dumps(payload_data, default=str)

            try:
                cache.set(self.cache_key, payload, timeout=CHECKPOINT_TTL)
            except Exception as cache_exc:
                logger.warning(
                    "checkpoint_save_failed",
                    extra={"error": str(cache_exc), "run_id": self.run_id},
                )

            checkpoint_file = self._file_path
            checkpoint_file.write_text(payload, encoding="utf-8")
            logger.debug("Checkpoint saved: %s", checkpoint_file)
            self._data = payload_data
            return True
        except Exception as exc:
            logger.error("checkpoint_file_save_failed: %s", exc)
            return False

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
        self.save(self._data)

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
