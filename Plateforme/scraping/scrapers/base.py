"""Core scraper orchestration without legacy HTTP parsing dependencies."""

from __future__ import annotations

import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from dateutil import parser as date_parser
from django.contrib.auth import get_user_model
from django.utils import timezone

from scraping.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_NAME, SYSTEM_USER_NAME_AR
from scraping.scrapers.base_dedup import DedupMixin
from scraping.scrapers.base_media import BaseMediaCompat, MediaMixin
from scraping.scrapers.base_text import TextMixin
from scraping.scraping_settings import scraping_settings as SS
from scraping.utils import infer_translation_status

logger = logging.getLogger(__name__)
User = get_user_model()


def handle_partial_data(item_data: dict) -> dict:
    """Fill frequently missing research fields with a traceable placeholder."""
    payload = dict(item_data or {})
    placeholder = "[NEEDS RESEARCH]"

    url_keys = (
        "url",
        "source_url",
        "website",
        "access_link",
        "download_url",
        "paper_url",
        "registration_link",
    )
    date_keys = (
        "date",
        "published_date",
        "start_date",
        "end_date",
        "deadline",
        "submission_deadline",
        "notification_date",
    )
    author_keys = (
        "author",
        "author_name",
        "created_by",
        "organizer",
        "institution_name",
    )
    law_reference_keys = (
        "law_reference",
        "legal_reference",
        "reference",
    )

    def _fill_group(keys: tuple[str, ...], canonical_key: str):
        group_has_value = any(str(payload.get(key) or "").strip() for key in keys)
        if not group_has_value:
            payload[canonical_key] = placeholder
            for key in keys:
                if key in payload and not str(payload.get(key) or "").strip():
                    payload[key] = placeholder

    def _fill_alias_if_missing(keys: tuple[str, ...], value: str):
        for key in keys:
            if key in payload and not str(payload.get(key) or "").strip():
                payload[key] = value

    _fill_group(url_keys, "url")
    _fill_group(author_keys, "author")
    _fill_group(law_reference_keys, "law_reference")

    url_value = str(payload.get("url") or "").strip()
    if url_value:
        _fill_alias_if_missing(url_keys, url_value)

    author_value = str(payload.get("author") or "").strip()
    if author_value:
        _fill_alias_if_missing(author_keys, author_value)

    # Never inject placeholders into date fields; keep them empty unless a real
    # date-like value already exists and can be mirrored across aliases.
    date_value = ""
    for key in date_keys:
        candidate = str(payload.get(key) or "").strip()
        if candidate:
            date_value = candidate
            break
    if date_value:
        _fill_alias_if_missing(date_keys, date_value)

    return payload


def emit_progress(
    run,
    step,
    current,
    total,
    message,
    current_source="",
    current_item="",
    *,
    items_created=0,
    items_skipped=0,
    items_failed=None,
):
    """Emit run progress to websocket and persist progress fields atomically."""
    if run is None:
        return

    run_id = str(getattr(run, "id", run) or "").strip()
    if not run_id:
        return

    step_value = str(step or "discovery")[:100]
    current_value = max(0, int(current or 0))
    total_value = max(0, int(total or 0))
    message_value = str(message or "")[:255]
    source_value = str(current_source or "")[:255]
    item_value = str(current_item or current_source or message or "")[:255]
    failed_value = max(
        0,
        int(items_skipped if items_failed is None else items_failed or 0),
    )
    percent_value = int((current_value / total_value) * 100) if total_value > 0 else 0

    try:
        from scraping.models import ScrapingRun

        ScrapingRun.objects.filter(id=run_id).update(
            progress_current=current_value,
            progress_total=total_value,
            current_step=step_value,
            current_message=message_value,
            current_source=source_value,
            current_item=item_value,
            items_created=max(0, int(items_created or 0)),
            items_skipped=max(0, int(items_skipped or 0)),
            items_failed=failed_value,
        )
    except Exception:
        logger.debug("scraper_progress_db_update_failed", exc_info=True)

    try:
        from scraping.tasks import push_scraping_progress

        push_scraping_progress(
            run_id,
            {
                "type": "scraping_event",
                "event_type": "progress",
                "status": "running",
                "step": step_value,
                "current": current_value,
                "total": total_value,
                "percent": percent_value,
                "progress": current_value,
                "progress_current": current_value,
                "progress_total": total_value,
                "items_created": max(0, int(items_created or 0)),
                "items_scraped": max(0, int(items_created or 0)),
                "items_failed": failed_value,
                "current_source": source_value,
                "current_item": item_value,
                "current_step": step_value,
                "current_message": message_value,
                "message": message_value,
            },
        )
    except Exception:
        logger.debug("scraper_progress_ws_emit_failed", exc_info=True)


class BaseScraper(TextMixin, MediaMixin, DedupMixin, ABC):
    """Shared run/persistence/dedup orchestration for category scrapers."""

    name: str = "Base Scraper"
    category: str = "unknown"
    MIN_CONFIDENCE_TO_SAVE: float = 0.35
    MIN_CONFIDENCE_PERCENT_TO_REVIEW: float = 50.0
    NEEDS_RESEARCH_PLACEHOLDER = "[NEEDS RESEARCH]"
    TERMINAL_REVIEW_STATUSES = {"APPROVED"}

    def __init__(self):
        self.results: list[dict] = []
        self.errors: list[str] = []
        self.structured_errors: list[dict] = []
        self.items_created: int = 0
        self.items_updated: int = 0
        self.items_flagged_for_review: int = 0
        self.items_skipped: int = 0
        self._progress_run = None
        self.validation_stats = {
            "passed": 0,
            "failed_date": 0,
            "failed_fields": 0,
            "failed_freshness": 0,
            "auto_filled": 0,
        }
        self._system_user = None
        self._last_duplicate_match_id = ""
        self._semantic_match_threshold = 90.0

    def bind_progress_run(self, run):
        """Bind a ScrapingRun instance used for progress updates."""
        self._progress_run = run

    def emit_progress(
        self,
        step: str = "discovery",
        current: int = 0,
        total: int = 0,
        message: str = "",
        *,
        current_source: str = "",
        current_item: str = "",
    ) -> None:
        """Emit progress for the currently bound run."""
        emit_progress(
            self._progress_run,
            step,
            current,
            total,
            message,
            current_source=current_source,
            current_item=current_item,
            items_created=self.items_created,
            items_skipped=self.items_skipped,
            items_failed=self.items_skipped,
        )

    def _confidence_payload(self, item_data: dict) -> dict:
        payload = dict(item_data or {})

        payload.setdefault(
            "title_en",
            payload.get("title_en")
            or payload.get("title")
            or payload.get("job_title")
            or payload.get("dataset_name")
            or "",
        )
        payload.setdefault(
            "description_en",
            payload.get("description_en")
            or payload.get("description")
            or payload.get("summary_en")
            or payload.get("content_en")
            or "",
        )
        payload.setdefault(
            "description_ar",
            payload.get("description_ar")
            or payload.get("summary_ar")
            or payload.get("content_ar")
            or "",
        )
        payload.setdefault(
            "url",
            payload.get("url")
            or payload.get("source_url")
            or payload.get("website")
            or payload.get("access_link")
            or payload.get("download_url")
            or payload.get("registration_link")
            or "",
        )

        if self.category == "news":
            payload.setdefault("published_date", payload.get("date") or "")

        if self.category == "courses":
            payload.setdefault("course_url", payload.get("url") or "")

        if self.category == "tools":
            payload.setdefault("keywords", payload.get("capabilities") or [])
            payload.setdefault(
                "supported_languages",
                payload.get("language_support")
                or ([payload.get("language")] if payload.get("language") else []),
            )
            payload.setdefault("language_support", payload.get("supported_languages"))

        if self.category == "opportunities":
            payload.setdefault(
                "institution",
                payload.get("institution") or payload.get("institution_name") or "",
            )

        if self.category == "corpus":
            payload.setdefault(
                "download_url", payload.get("download_url") or payload.get("url") or ""
            )
            payload.setdefault(
                "size", payload.get("size") or payload.get("size_estimate") or ""
            )

        return payload

    def passes_min_confidence_to_save(self, item_data: dict) -> bool:
        if isinstance(item_data, dict):
            item_data.update(handle_partial_data(item_data))

        confidence = 0.0
        quality_messages: list[str] = []
        try:
            from scraping.intelligence import calculate_item_confidence
            from scraping.validators.content_validator import ExtractionQualityValidator

            payload = self._confidence_payload(item_data)
            payload = handle_partial_data(payload)

            confidence_report = calculate_item_confidence(self.category, payload)
<<<<<<< HEAD
            confidence_percent = max(
                0.0,
                min(100.0, float(confidence_report.get("percent", 0.0))),
            )
            confidence = confidence_percent / 100.0
=======
            confidence = max(0.0, min(1.0, float(confidence_report.get("score", 0.0))))
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

            if isinstance(item_data, dict):
                item_data["extraction_confidence"] = round(confidence, 3)

            payload["extraction_confidence"] = round(confidence, 3)

            validator = ExtractionQualityValidator()
            is_valid, quality_messages = validator.validate(payload, self.category)
            if not is_valid:
                logger.info(
                    "candidate_rejected_quality_validation: %s (confidence=%.3f) reasons=%s",
                    self._item_display_name(item_data),
                    confidence,
                    quality_messages,
                    extra={
                        "category": self.category,
                        "source_name": self.name,
                        "item_title": self._item_display_name(item_data),
                        "messages": quality_messages,
                    },
                )
        except Exception:
            logger.debug("candidate_confidence_compute_failed", exc_info=True)

        confidence_percent = self._to_confidence_percent(
            confidence if confidence else (item_data or {}).get("confidence_score")
        )
        review_status = (
            "PENDING_REVIEW"
            if confidence_percent >= self.MIN_CONFIDENCE_PERCENT_TO_REVIEW
            else "REJECTED"
        )

        if isinstance(item_data, dict):
            item_data["confidence_score"] = round(confidence_percent, 1)
            item_data["scrape_status"] = review_status
            item_data["approval_status"] = (
                "pending" if review_status == "PENDING_REVIEW" else "rejected"
            )
            if quality_messages:
                existing_notes = str(item_data.get("validation_notes") or "").strip()
                quality_note = "; ".join(
                    str(msg).strip() for msg in quality_messages if str(msg).strip()
                )
                if quality_note:
                    item_data["validation_notes"] = (
                        f"{existing_notes}; {quality_note}"
                        if existing_notes
                        else quality_note
                    )
            if review_status == "REJECTED":
                note = "Auto-rejected: confidence_score below 50%."
                existing_notes = str(item_data.get("validation_notes") or "").strip()
                if note not in existing_notes:
                    item_data["validation_notes"] = (
                        f"{existing_notes}; {note}" if existing_notes else note
                    )

        logger.info(
            "candidate_review_decision",
            extra={
                "category": self.category,
                "source_name": self.name,
                "confidence": round(confidence_percent, 1),
                "review_status": review_status,
                "item_title": self._item_display_name(item_data),
            },
        )
        return True

    @staticmethod
    def _to_confidence_percent(value) -> float:
        try:
            if value is None:
                return 0.0
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0

        if numeric <= 1.0:
            numeric *= 100.0
        return max(0.0, min(100.0, numeric))

    def _track_saved_item_status(self, item_data: dict | None) -> None:
        status = str((item_data or {}).get("scrape_status") or "").strip().upper()
        approval_status = (
            str((item_data or {}).get("approval_status") or "").strip().lower()
        )
        if status == "PENDING_REVIEW" or approval_status == "pending":
            self.items_flagged_for_review += 1

    def _is_terminal_review_status(self, status: str | None) -> bool:
        return str(status or "").strip().upper() in self.TERMINAL_REVIEW_STATUSES

    def _is_approved_record(self, existing_obj) -> bool:
        scrape_status = (
            str(getattr(existing_obj, "scrape_status", "") or "").strip().upper()
        )
        approval_status = (
            str(getattr(existing_obj, "approval_status", "") or "").strip().lower()
        )
        return scrape_status == "APPROVED" or approval_status == "approved"

    def _is_needs_research_value(self, value) -> bool:
        return (
            isinstance(value, str)
            and value.strip().upper() == self.NEEDS_RESEARCH_PLACEHOLDER.upper()
        )

    @staticmethod
    def _strip_diacritics(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        return "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

    @staticmethod
    def _transliterate_to_phonetic(value: str) -> str:
        transliteration_map = {
            "ء": "",
            "أ": "a",
            "إ": "i",
            "آ": "a",
            "ا": "a",
            "ب": "b",
            "ت": "t",
            "ث": "th",
            "ج": "j",
            "ح": "h",
            "خ": "kh",
            "د": "d",
            "ذ": "dh",
            "ر": "r",
            "ز": "z",
            "س": "s",
            "ش": "sh",
            "ص": "s",
            "ض": "d",
            "ط": "t",
            "ظ": "z",
            "ع": "a",
            "غ": "gh",
            "ف": "f",
            "ق": "q",
            "ك": "k",
            "ل": "l",
            "م": "m",
            "ن": "n",
            "ه": "h",
            "ة": "h",
            "و": "w",
            "ؤ": "w",
            "ي": "y",
            "ى": "y",
            "ئ": "y",
            "ـ": "",
        }
        return "".join(
            transliteration_map.get(character, character) for character in value
        )

    def get_semantic_hash(self, title: str | None) -> str:
        """Normalize titles for cross-script phonetic matching."""
        text = self._strip_diacritics(str(title or "")).lower().strip()
        if not text:
            return ""

        has_arabic = bool(re.search(r"[\u0600-\u06ff]", text))
        text = self._transliterate_to_phonetic(text)
        text = re.sub(r"[^a-z0-9\s]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        tokens: list[str] = []
        prefix_tokens = {"the"}
        for raw_token in text.split():
            token = raw_token.strip().lower()
            if not token or token in prefix_tokens:
                continue
            if has_arabic and token in {"al", "el", "il", "ul"}:
                continue
            token = re.sub(r"^[aeiouy]+", "", token)
            token = re.sub(r"(.)\1+", r"\1", token)
            token = re.sub(r"[^a-z0-9]", "", token)
            if token:
                tokens.append(token)

        return " ".join(tokens)

    def _semantic_title_similarity(self, left: str | None, right: str | None) -> float:
        left_hash = self.get_semantic_hash(left)
        right_hash = self.get_semantic_hash(right)
        if not left_hash or not right_hash:
            return 0.0
        if left_hash == right_hash:
            return 100.0
        return SequenceMatcher(None, left_hash, right_hash).ratio() * 100.0

    def _find_semantic_title_match(
        self,
        queryset,
        incoming_title: str | None,
        *,
        title_fields: tuple[str, ...] = ("title_en", "title"),
    ):
        incoming_hash = self.get_semantic_hash(incoming_title)
        if not incoming_hash:
            return None, 0.0

        best_match = None
        best_score = 0.0
        for existing_obj in queryset:
            existing_title = ""
            for field_name in title_fields:
                candidate_value = str(
                    getattr(existing_obj, field_name, "") or ""
                ).strip()
                if candidate_value:
                    existing_title = candidate_value
                    break
            if not existing_title:
                continue

            score = self._semantic_title_similarity(incoming_title, existing_title)
            if score > best_score:
                best_match = existing_obj
                best_score = score
            if score >= self._semantic_match_threshold:
                return existing_obj, score

        if best_match is not None and best_score >= self._semantic_match_threshold:
            return best_match, best_score
        return None, best_score

    def _build_terminal_status_update_defaults(
        self,
        *,
        existing_obj,
        incoming_defaults: dict,
        metadata_fields: set[str] | None = None,
    ) -> dict:
        """Keep approved moderation status and only update metadata + [NEEDS RESEARCH] fields."""
        allowed_metadata = set(metadata_fields or set())
        safe_defaults: dict = {}

        for field_name, field_value in incoming_defaults.items():
            if field_name in allowed_metadata:
                safe_defaults[field_name] = field_value
                continue

            if not hasattr(existing_obj, field_name):
                continue

            existing_value = getattr(existing_obj, field_name)
            if not self._is_needs_research_value(existing_value):
                continue

            if field_value is None:
                continue
            if isinstance(field_value, str) and not field_value.strip():
                continue

            safe_defaults[field_name] = field_value

        if hasattr(existing_obj, "scrape_status"):
            safe_defaults["scrape_status"] = str(
                existing_obj.scrape_status or ""
            ).upper()
        if hasattr(existing_obj, "approval_status"):
            safe_defaults["approval_status"] = str(
                existing_obj.approval_status or ""
            ).lower()

        return safe_defaults

    @abstractmethod
    def scrape(self):
        """Execute category-specific scraping logic."""

    def run(self) -> dict:
        logger.info(
            "scraper_started",
            extra={
                "category": self.category,
                "source_name": self.name,
            },
        )

        self.emit_progress(
            "discovery",
            0,
            4,
            "Initializing scraper run",
            current_source=self.name,
            current_item=self.name,
        )
        self._disable_es_indexing()
        try:
            self.emit_progress(
                "extraction",
                1,
                4,
                "Running extraction pipeline",
                current_source=self.name,
                current_item=self.name,
            )
            self.scrape()
        except Exception as exc:
            self._log_error("scraper_crash", str(exc), source=self.name)
            self.emit_progress(
                "saving",
                4,
                4,
                f"Scraper failed: {str(exc)[:80]}",
                current_source=self.name,
                current_item=self.name,
            )
            logger.exception("Scraper %s failed", self.name)
        finally:
            self._enable_es_indexing()

        self.emit_progress(
            "validation",
            3,
            4,
            "Computing intelligence scores",
            current_source=self.name,
            current_item=self.name,
        )
        intelligence_summary = self._run_intelligence()
        self.emit_progress(
            "saving",
            4,
            4,
            "Scraping run completed",
            current_item="",
        )

        return {
            "scraper": self.name,
            "category": self.category,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "items_flagged_for_review": self.items_flagged_for_review,
            "items_skipped": self.items_skipped,
            "items_found": self.items_created + self.items_updated + self.items_skipped,
            "total_created": self.items_created,
            "total_updated": self.items_updated,
            "total_flagged_for_review": self.items_flagged_for_review,
            "errors": self.errors,
            "structured_errors": self.structured_errors,
            "results": self.results,
            "intelligence": intelligence_summary,
            "validation_stats": dict(self.validation_stats),
        }

    def get_active_search_queries(self, category: str | None = None) -> list[str]:
        """Return active DB-backed search queries for a scraper category."""
        from scraping.models import SearchQuery

        target_category = (category or self.category or "").strip().lower()
        if not target_category:
            return []

        try:
            queryset = (
                SearchQuery.objects.filter(
                    category=target_category,
                    is_active=True,
                )
                .only("query_text")
                .order_by("id")
            )
        except Exception as exc:
            self._log_error(
                "search_query_lookup_failed",
                str(exc),
                source=self.name,
            )
            return []

        queries: list[str] = []
<<<<<<< HEAD
        max_active_prompts = max(
            1,
            min(
                int(getattr(SS, "PROMPT_MAX_ACTIVE_PER_CATEGORY", 20) or 20),
                200,
            ),
        )
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        for row in queryset:
            query_text = (row.query_text or "").strip()
            if query_text:
                queries.append(query_text)
<<<<<<< HEAD
            if len(queries) >= max_active_prompts:
                break
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        return queries

    def _disable_es_indexing(self):
        try:
            from django_elasticsearch_dsl.registries import registry

            self._original_es_update = registry.update
            self._original_es_delete = registry.delete
            registry.update = lambda *a, **kw: None
            registry.delete = lambda *a, **kw: None
        except Exception:
            logger.debug("es_indexing_disable_skipped", exc_info=True)

    def _enable_es_indexing(self):
        try:
            from django_elasticsearch_dsl.registries import registry

            if hasattr(self, "_original_es_update"):
                registry.update = self._original_es_update
            if hasattr(self, "_original_es_delete"):
                registry.delete = self._original_es_delete
        except Exception:
            logger.debug("es_indexing_enable_skipped", exc_info=True)

    def _log_error(
        self,
        error_type: str,
        message: str,
        source: str = "",
        url: str = "",
        extra: dict | None = None,
    ):
        full_message = f"{error_type}: {message}"
        self.errors.append(full_message)

        entry = {
            "type": error_type,
            "message": message,
            "source": source or self.name,
            "url": url,
            "timestamp": timezone.now().isoformat(),
        }
        if extra:
            entry["extra"] = extra

        self.structured_errors.append(entry)
        logger.warning(
            "[%s] %s - %s (source=%s url=%s)",
            self.category,
            error_type,
            message,
            source or self.name,
            url,
        )

    def _notify_skip(self, name: str, url: str, reason: str):
        payload = {
            "name": name,
            "url": url,
            "reason": reason,
            "category": self.category,
            "source_name": self.name,
        }
        run = getattr(self, "_progress_run", None) or getattr(self, "run", None)
        run_id = str(getattr(run, "id", "") or "")
        if not run_id:
            return

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        try:
            async_to_sync(channel_layer.group_send)(
                f"scraping_{run_id}",
                {
                    "type": "scraping_event",
                    "event_type": "item_skipped",
                    "run_id": run_id,
                    "task_uuid": run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **payload,
                },
            )
        except Exception:
            logger.debug("notify_skip_dispatch_failed", exc_info=True)

    def _is_download_enabled(self) -> bool:
        return bool(getattr(SS, "DOWNLOAD_ATTACHMENTS", True))

    def _max_concurrent_downloads(self) -> int:
        value = int(getattr(SS, "MAX_CONCURRENT_DOWNLOADS", 4))
        return max(1, value)

    @staticmethod
    def _coerce_url_list(value) -> list[str]:
        return BaseMediaCompat._coerce_url_list_fallback(value)

    def _collect_page_media_urls(self, page_url: str, category: str) -> dict:
        del page_url
        del category
        return {
            "image_urls": [],
            "pdf_urls": [],
        }

    def _resolve_media_candidates(self, item_data: dict, category: str) -> dict:
        del category
        image_candidates = self._coerce_url_list(
            item_data.get("image_url")
            or item_data.get("thumbnail")
            or item_data.get("banner_image")
        )
        pdf_candidates = self._coerce_url_list(
            item_data.get("pdf_url")
            or item_data.get("file_url")
            or item_data.get("attachment")
        )
        return {
            "image_urls": image_candidates,
            "pdf_urls": pdf_candidates,
        }

    def _download_media(self, item_data: dict, category: str) -> dict:
        del category
        item_data = dict(item_data or {})
        item_data.setdefault("image_local_path", "")
        item_data.setdefault("image_content_file", None)
        item_data.setdefault("pdf_local_path", "")
        item_data.setdefault("pdf_content_file", None)
        return item_data

    def get_system_user(self):
        user_model = get_user_model()

        if self._system_user is not None:
            return self._system_user

        user = user_model.objects.filter(email=SYSTEM_USER_EMAIL).first()
        if user is None:
            try:
                user = user_model.objects.create_user(
                    email=SYSTEM_USER_EMAIL,
                    password=None,
                    full_name=SYSTEM_USER_NAME,
                    full_name_en=SYSTEM_USER_NAME,
                    full_name_ar=SYSTEM_USER_NAME_AR,
                )
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                if hasattr(user, "is_verified"):
                    user.is_verified = True
                if hasattr(user, "is_email_verified"):
                    user.is_email_verified = True
                user.save()
            except Exception:
                user = user_model.objects.filter(is_superuser=True).first()

        if user is None:
            raise RuntimeError(
                "Cannot resolve a system scraper user. Create a superuser first."
            )

        self._system_user = user
        return user

    def get_or_create_country(self, name_en: str, code: str = "", name_ar: str = ""):
        from institutions.models import Country

        normalized_code = (code or name_en[:2]).upper()[:2]
        country, _ = Country.objects.get_or_create(
            code=normalized_code,
            defaults={
                "name_en": name_en,
                "name_ar": name_ar or name_en,
            },
        )
        return country

    def get_or_create_institution(self, name: str, **kwargs):
        from institutions.models import Institution

        normalized_name = (name or "").strip()
        if not normalized_name:
            return None

        existing = Institution.objects.filter(name_en__iexact=normalized_name).first()
        if existing is not None:
            return existing

        country = kwargs.get("country") or self.get_or_create_country(
            "International", "XX"
        )
        city = (kwargs.get("city") or "").strip()
        website = (kwargs.get("website") or "").strip()
        description = kwargs.get("description") or (
            f"{normalized_name} is a research institution active in natural "
            "language processing and computational linguistics."
        )
        country_name = getattr(country, "name_en", "")
        address = f"{city}, {country_name}" if city else country_name

        try:
            return Institution.objects.create(
                name=normalized_name,
                name_en=normalized_name,
                name_ar=(kwargs.get("name_ar") or normalized_name)[:255],
                acronym=(kwargs.get("acronym") or "")[:50],
                type=(kwargs.get("inst_type") or "University")[:50],
                country=country,
                city_en=city,
                city=city,
                city_ar=city,
                website=website,
                email=(kwargs.get("email") or "")[:254],
                phone=(kwargs.get("phone") or "")[:50],
                address=address,
                address_en=address,
                address_ar=address,
                description=description,
                description_en=description,
                description_ar=description,
                created_by=self.get_system_user(),
            )
        except Exception as exc:
            self._log_error(
                "institution_create",
                str(exc),
                source=normalized_name,
                url=website,
            )
            return None

    @staticmethod
    def _normalize_text(value: str) -> str:
<<<<<<< HEAD
        if not value:
            return ""
        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", value).lower()
        # Remove common stop words to focus on meaningful tokens
        stop_words = {"a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "of", "by"}
        tokens = [t for t in text.split() if t not in stop_words]
        return " ".join(tokens).strip()
=======
        return re.sub(r"\s+", " ", (value or "")).strip().lower()
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    @staticmethod
    def _normalize_url(value: str, strip_www: bool = False) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""

        parsed = urlparse(raw)
        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()
        if strip_www and netloc.startswith("www."):
            netloc = netloc[4:]
        path = (parsed.path or "").rstrip("/")
        return f"{scheme}://{netloc}{path}"

    @staticmethod
    def _title_similarity(left: str, right: str) -> float:
<<<<<<< HEAD
        l_norm = BaseScraper._normalize_text(left)
        r_norm = BaseScraper._normalize_text(right)
        
        if not l_norm or not r_norm:
            return 0.0
            
        s1 = set(l_norm.split())
        s2 = set(r_norm.split())
        
        if not s1 and not s2:
            return 1.0
        
        jaccard = len(s1 & s2) / len(s1 | s2)
        
        # Fallback to SequenceMatcher for very short strings
        if len(s1) <= 2 or len(s2) <= 2:
            seq_match = SequenceMatcher(None, l_norm, r_norm).ratio()
            return max(jaccard, seq_match)
            
        return jaccard
=======
        return SequenceMatcher(
            None,
            BaseScraper._normalize_text(left),
            BaseScraper._normalize_text(right),
        ).ratio()
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    @staticmethod
    def _extract_instructor(value: str) -> str:
        text = value or ""
        match = re.search(r"(?:instructor|teacher)\s*[:\-]\s*([^\n\r]+)", text, re.I)
        if match is None:
            return ""
        return BaseScraper._normalize_text(match.group(1))

    @staticmethod
    def _item_display_name(item_data: dict) -> str:
        for key in ("title_en", "title", "name_en", "name"):
            value = (item_data.get(key) or "").strip()
            if value:
                return value
        return "untitled"

    def _set_duplicate_match(self, existing_obj):
        self._last_duplicate_match_id = str(getattr(existing_obj, "id", ""))

    def _record_duplicate_skip(
        self, category: str, item_data: dict, reason: str, match_score: float = 0.0
    ):
        item_label = self._item_display_name(item_data)
        matched_id = getattr(self, "_last_duplicate_match_id", "")
        reason_code = self._normalize_skip_reason(reason)
        logger.info(
            "item_skipped",
            extra={
                "category": category,
                "source_name": self.name,
                "item_title": item_label,
                "item_id": matched_id or "unknown",
                "skip_reason": reason_code,
            },
        )

        try:
            from scraping.models import ScrapedItemMeta

            ScrapedItemMeta.objects.update_or_create(
                category=category,
                item_title=item_label[:300],
                defaults={
                    "item_id": matched_id,
                    "skip_reason": reason_code,
                    "source_name": item_data.get("source_name") or self.name,
                    "source_url": item_data.get("source_url") or "",
                    "match_score": match_score,
                    "matched_item_id": matched_id or None,
                    "was_skipped": True,
                    "translation_status": (
                        str(item_data.get("translation_status") or "").strip()
                        or "pending"
                    ),
                },
            )
        except Exception as exc:
            self._log_error("dedup_skip_meta", str(exc), source=item_label)

    @staticmethod
    def _normalize_skip_reason(reason: str) -> str:
        lowered = BaseScraper._normalize_text(reason or "")
        if "url" in lowered or "website" in lowered or "link" in lowered:
            return "dedup_url"
        if "name" in lowered or "title" in lowered or "exact" in lowered:
            return "dedup_name"
        return "dedup_similarity"

    @staticmethod
    def _recent_dedup_queryset(queryset):
        field_names = {field.name for field in queryset.model._meta.fields}
        order_field = "-created_at" if "created_at" in field_names else "-id"
        return queryset.order_by(order_field)[: int(getattr(SS, "DEDUP_WINDOW", 300))]

    def _dedup_event(self, item_data: dict) -> tuple[bool, str, float]:
        from events.models import Event

        website_url = (
            item_data.get("website_url") or item_data.get("website") or ""
        ).strip()
        if website_url:
            existing = Event.objects.filter(website__iexact=website_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "event website_url exact match", 1.0

        organizer = item_data.get("organizer")
        start_date = item_data.get("start_date")
        end_date = item_data.get("end_date")
        if organizer and start_date and end_date:
            # Keep a 3-day tolerance around ranges for real-world date drift.
            window_start = start_date - timedelta(days=3)
            window_end = end_date + timedelta(days=3)
            overlap = (
                Event.objects.filter(organizer=organizer)
                .filter(start_date__lte=window_end, end_date__gte=window_start)
                .first()
            )
            if overlap:
                self._set_duplicate_match(overlap)
                return True, "event organizer overlapping date range", 0.9

        candidate_title = item_data.get("title_en") or item_data.get("title") or ""
        if candidate_title:
            recent_events = self._recent_dedup_queryset(
                Event.objects.only("id", "title", "title_en")
            )
            threshold = float(getattr(SS, "JACCARD_THRESHOLD", 0.85))
            for event in recent_events:
                existing_title = event.title_en or event.title
                similarity = self._title_similarity(candidate_title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(event)
                    return (
                        True,
                        f"event title similarity >= {int(threshold * 100)}%",
                        similarity,
                    )

        return False, "", 0.0

    def _dedup_tool(self, item_data: dict) -> tuple[bool, str, float]:
        from resources.models import NLPTool

        github_url = (item_data.get("github_url") or "").strip()
        if github_url:
            existing = NLPTool.objects.filter(github_url__iexact=github_url).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool github_url exact match", 1.0

        access_link = (item_data.get("access_link") or "").strip()
        if access_link:
            existing = NLPTool.objects.filter(access_link__iexact=access_link).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "tool access_link exact match", 1.0

        title = item_data.get("title_en") or item_data.get("title") or ""
        if title:
            recent_tools = self._recent_dedup_queryset(
                NLPTool.objects.only("id", "title", "title_en")
            )
            normalized_title = self._normalize_text(title)
            for tool in recent_tools:
                existing_title = tool.title_en or tool.title
                if self._normalize_text(existing_title) == normalized_title:
                    self._set_duplicate_match(tool)
                    return True, "tool name exact match", 1.0

            threshold = float(getattr(SS, "STRICT_JACCARD", 0.9))
            for tool in recent_tools:
                existing_title = tool.title_en or tool.title
                similarity = self._title_similarity(title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(tool)
                    return (
                        True,
                        f"tool title similarity >= {int(threshold * 100)}%",
                        similarity,
                    )

            try:
                from scraping.embeddings import find_semantic_duplicate

                semantic_match = find_semantic_duplicate(title, "tools", threshold=0.88)
                if semantic_match is not None:
                    self._set_duplicate_match(semantic_match)
                    return True, "tool semantic similarity", 0.88
            except Exception:
                logger.debug("tool_semantic_dedup_check_failed", exc_info=True)

        return False, "", 0.0

    def _dedup_news(self, item_data: dict) -> tuple[bool, str, float]:
        from feed.models import Post

        arxiv_id = (item_data.get("arxiv_id") or "").strip()
        if arxiv_id:
            existing = Post.objects.filter(arxiv_id__iexact=arxiv_id).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "news arxiv_id exact match", 1.0

        doi = (item_data.get("doi") or "").strip()
        if doi:
            existing = Post.objects.filter(doi__iexact=doi).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "news doi exact match", 1.0

        source_url = (item_data.get("source_url") or "").strip()
        if source_url:
            normalized = self._normalize_url(source_url, strip_www=True)
            for post in self._recent_dedup_queryset(
                Post.objects.only("id", "source_url")
            ):
                existing_url = self._normalize_url(
                    getattr(post, "source_url", ""), strip_www=True
                )
                if existing_url and existing_url == normalized:
                    self._set_duplicate_match(post)
                    return True, "news source_url exact match", 1.0

        title = item_data.get("title_en") or item_data.get("title") or ""
        if title:
            threshold = float(getattr(SS, "JACCARD_THRESHOLD", 0.85))
            for post in self._recent_dedup_queryset(
                Post.objects.only("id", "title", "title_en")
            ):
                existing_title = post.title_en or post.title
                similarity = self._title_similarity(title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(post)
                    return (
                        True,
                        f"news title similarity >= {int(threshold * 100)}%",
                        similarity,
                    )

        return False, "", 0.0

    def _dedup_course(self, item_data: dict) -> tuple[bool, str, float]:
        from resources.models import Course

        access_link = (
            item_data.get("course_url") or item_data.get("access_link") or ""
        ).strip()
        if access_link:
            existing = Course.objects.filter(access_link__iexact=access_link).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "course access_link exact match", 1.0

        title = item_data.get("title_en") or item_data.get("title") or ""
        if title:
            instructor = self._normalize_text(item_data.get("instructor") or "")
            recent_courses = self._recent_dedup_queryset(
                Course.objects.only(
                    "id", "title", "title_en", "description", "description_en"
                )
            )
            normalized_title = self._normalize_text(title)
            for course in recent_courses:
                existing_title = course.title_en or course.title
                if self._normalize_text(existing_title) != normalized_title:
                    continue
                if instructor:
                    existing_instructor = self._extract_instructor(
                        f"{getattr(course, 'description_en', '')}\n{getattr(course, 'description', '')}"
                    )
                    if existing_instructor and existing_instructor == instructor:
                        self._set_duplicate_match(course)
                        return True, "course title + instructor", 1.0

            threshold = float(getattr(SS, "STRICT_JACCARD", 0.9))
            for course in recent_courses:
                existing_title = course.title_en or course.title
                similarity = self._title_similarity(title, existing_title)
                if similarity >= threshold:
                    self._set_duplicate_match(course)
                    return (
                        True,
                        f"course title similarity >= {int(threshold * 100)}%",
                        similarity,
                    )

        return False, "", 0.0

    def _dedup_institution(self, item_data: dict) -> tuple[bool, str, float]:
        from institutions.models import Institution

        ror_id = (item_data.get("ror_id") or "").strip()
        if ror_id:
            existing = Institution.objects.filter(ror_id__iexact=ror_id).first()
            if existing:
                self._set_duplicate_match(existing)
                return True, "institution ror_id exact match", 1.0

        website_url = (
            item_data.get("website_url") or item_data.get("website") or ""
        ).strip()
        if website_url:
            normalized = self._normalize_url(website_url, strip_www=True)
            for institution in self._recent_dedup_queryset(
                Institution.objects.only("id", "website")
            ):
                existing_website = self._normalize_url(
                    getattr(institution, "website", ""), strip_www=True
                )
                if existing_website and existing_website == normalized:
                    self._set_duplicate_match(institution)
                    return True, "institution website_url exact match", 1.0

        name = item_data.get("name_en") or item_data.get("name") or ""
        if name:
            threshold = float(getattr(SS, "STRICT_JACCARD", 0.9))
            for institution in self._recent_dedup_queryset(
                Institution.objects.only("id", "name", "name_en")
            ):
                existing_name = institution.name_en or institution.name
                similarity = self._title_similarity(name, existing_name)
                if similarity >= threshold:
                    self._set_duplicate_match(institution)
                    return (
                        True,
                        f"institution name similarity >= {int(threshold * 100)}%",
                        similarity,
                    )

        return False, "", 0.0

    def _check_duplicate_policy(self, category, item_data) -> tuple[bool, str, float]:
        checker_map = {
            "events": self._dedup_event,
            "tools": self._dedup_tool,
            "courses": self._dedup_course,
            "news": self._dedup_news,
            "institutions": self._dedup_institution,
        }
        checker = checker_map.get((category or "").strip().lower())
        if checker is None:
            return False, "", 0.0

        is_duplicate, reason, score = checker(item_data)
        if is_duplicate:
            self._record_duplicate_skip(category, item_data, reason, match_score=score)
            return is_duplicate, reason, score

        # Semantic fallback is intentionally centralized here so categories that
        # do not implement their own semantic checks still benefit from it.
        normalized_category = (category or "").strip().lower()
        title = item_data.get("title_en") or item_data.get("title") or ""
        if normalized_category == "news" and title:
            try:
                from scraping.embeddings import find_semantic_duplicate

                semantic_match = find_semantic_duplicate(
                    title,
                    normalized_category,
                    threshold=0.88,
                )
                if semantic_match is not None:
                    self._set_duplicate_match(semantic_match)
                    reason = f"{normalized_category} semantic fallback"
                    score = 0.88
                    self._record_duplicate_skip(
                        category,
                        item_data,
                        reason,
                        match_score=score,
                    )
                    return True, reason, score
            except Exception:
                logger.debug("semantic_dedup_fallback_check_failed", exc_info=True)

        return False, "", 0.0

    def is_duplicate(self, title, category, model_class):
        del model_class
        payload = {
            "title": title,
            "title_en": title,
        }
        is_duplicate, _, _ = self._check_duplicate_policy(category, payload)
        return is_duplicate

    @staticmethod
    def parse_date(
        date_str: str | None,
        default: datetime | None = None,
    ) -> datetime | None:
        if not date_str:
            return default
        try:
            parsed = date_parser.parse(date_str, fuzzy=True)
            if isinstance(parsed, datetime):
                return parsed
            return datetime.combine(parsed, datetime.min.time())
        except (ValueError, OverflowError, TypeError):
            return default

    @staticmethod
    def truncate(text: str, max_len: int = 200) -> str:
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        cleaned = re.sub(r"\s+", " ", text).strip()
        if self.detect_arabic_ratio(cleaned) > 0.1:
            cleaned = self.normalize_arabic_text(cleaned)
        return cleaned

    def normalize_arabic_text(self, text):
        if not text or not text.strip():
            return text
        try:
            import pyarabic.araby as araby

            normalized = araby.strip_tashkeel(text)
            normalized = araby.normalize_alef(normalized)
            normalized = araby.normalize_lamalef(normalized)
            return normalized.strip()
        except Exception:
            normalized = re.sub(r"[\u0617-\u061A\u064B-\u065F]", "", text)
            normalized = re.sub(r"[أإآ]", "ا", normalized)
            normalized = re.sub(r"ة", "ه", normalized)
            return normalized.strip()

    def detect_arabic_ratio(self, text):
        if not text or not text.strip():
            return 0.0
        arabic_chars = len(
            re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text)
        )
        alpha_chars = len(re.findall(r"[^\W\d_]", text))
        if alpha_chars == 0:
            return 0.0
        return arabic_chars / alpha_chars

    def detect_language(self, text: str) -> str:
        if not text or len(text.strip()) < 20:
            return "unknown"

        if self.detect_arabic_ratio(text) >= 0.30:
            return "ar"

        try:
            from langdetect import DetectorFactory, detect

            DetectorFactory.seed = 0
            detected = detect(text)
            if detected in {"ar", "fr", "en"}:
                return detected
            return "unknown"
        except Exception:
            return "unknown"

    def is_relevant_language(self, text):
        language = self.detect_language(text)
        return language in {"ar", "fr", "en"}

    def _run_intelligence(self) -> dict:
        try:
            from scraping.field_mapping import calculate_completeness_score
            from scraping.intelligence import (
                classify_domain,
                classify_domain_primary,
                compute_relevance_score,
            )
            from scraping.models import ScrapedItemMeta
        except Exception as exc:
            return {
                "status": "skipped",
                "reason": str(exc),
            }

        scored = 0
        domain_counts: dict[str, int] = {}
        avg_score = 0.0

        for item in self.results:
            title = item.get("title", "")
            if not title:
                continue

            description_text = (
                item.get("description")
                or item.get("description_en")
                or item.get("summary_en")
                or item.get("content_en")
                or ""
            )
            arabic_text = " ".join(
                str(item.get(key) or "")
                for key in (
                    "title_ar",
                    "description_ar",
                    "summary_ar",
                    "content_ar",
                )
            ).strip()
            text = " ".join(
                part
                for part in (
                    str(title or "").strip(),
                    str(description_text or "").strip(),
                    str(item.get("type") or "").strip(),
                    arabic_text,
                )
                if part
            )

            translation_status = infer_translation_status(
                raw_status=str(item.get("translation_status") or ""),
                english_values=[
                    item.get("title_en") or item.get("title"),
                    item.get("description_en")
                    or item.get("summary_en")
                    or item.get("content_en")
                    or item.get("description"),
                ],
                arabic_values=[
                    item.get("title_ar"),
                    item.get("description_ar")
                    or item.get("summary_ar")
                    or item.get("content_ar"),
                ],
            )

            domain_scores = classify_domain(text)
            primary_domain = classify_domain_primary(text)
            confidence_payload = self._confidence_payload(item)
            score = compute_relevance_score(
                category=self.category,
                item_data=confidence_payload,
                translation_status=translation_status,
            )

            if isinstance(item, dict):
                item.setdefault("extraction_confidence", round(float(score) / 100.0, 3))

            completeness = calculate_completeness_score(item, self.category)
            defaults = {
                "domain_scores": domain_scores,
                "primary_domain": primary_domain,
                "relevance_score": score,
                "completeness_score": completeness,
                "source_name": item.get("source_name") or self.name,
                "source_url": item.get("source_url") or item.get("url") or "",
                "was_skipped": False,
                "enrichment_status": "not_enriched",
                "translation_status": translation_status,
            }

            try:
                ScrapedItemMeta.objects.update_or_create(
                    category=self.category,
                    item_title=(item.get("title_en") or title)[:300],
                    defaults=defaults,
                )
            except Exception:
                logger.debug("intelligence_meta_update_failed", exc_info=True)

            scored += 1
            avg_score += score
            domain_counts[primary_domain] = domain_counts.get(primary_domain, 0) + 1

        return {
            "status": "completed",
            "items_scored": scored,
            "avg_relevance_score": round(avg_score / max(scored, 1), 1),
            "domain_distribution": domain_counts,
        }
