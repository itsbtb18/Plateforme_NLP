import logging
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, models, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest, Least
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

try:
    from pgvector.django import VectorField
except Exception:  # pragma: no cover - optional dependency at runtime
    VectorField = None

from scraping.constants import (
    CANONICAL_CATEGORIES,
    CATEGORY_META,
    DEDUP_EMBEDDING_DIM,
    DEDUP_EMBEDDING_MODEL,
    SKIP_CIRCUIT_OPEN,
    SKIP_DEDUP_ARXIV,
    SKIP_DEDUP_DOI,
    SKIP_DEDUP_EMBEDDING,
    SKIP_DEDUP_NAME,
    SKIP_DEDUP_ROR,
    SKIP_DEDUP_SIMILARITY,
    SKIP_DEDUP_URL,
    SKIP_DOWNLOAD_FAIL,
    SKIP_ENRICHMENT_FAIL,
    SKIP_VALIDATION_FAIL,
)
from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)


SCRAPER_CATEGORY_CHOICES = [
    (
        category,
        _(CATEGORY_META.get(category, {}).get("label", category.title())),
    )
    for category in CANONICAL_CATEGORIES
]

SCRAPER_CATEGORY_LABELS = dict(SCRAPER_CATEGORY_CHOICES)


def _vector_field_enabled() -> bool:
    if VectorField is None:
        return False

    if getattr(settings, "SCRAPING_DISABLE_VECTOR_FIELD", False):
        return False

    engine = str(settings.DATABASES.get("default", {}).get("ENGINE", ""))
    return "postgresql" in engine


class ScrapingSource(models.Model):
    """Configurable scraping source definition."""

    SCRAPE_CONFIG_PAGINATION_KEYS = {
        "max_pages": "int - max listing pages per path/source (bounded by SCRAPING_MAX_PAGES_HARD_LIMIT)",
        "page_param": "str - query parameter used for page number (default: 'page')",
        "start_page": "int - first page index when pagination starts (default: 1)",
    }

    CATEGORY_CHOICES = [
        (
            category,
            SCRAPER_CATEGORY_LABELS.get(
                category, _(category.replace("_", " ").title())
            ),
        )
        for category in CANONICAL_CATEGORIES
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Source Name"), max_length=200)
    category = models.CharField(_("Category"), max_length=50, choices=CATEGORY_CHOICES)
    url = models.URLField(_("URL"), blank=True, default="")
    base_url = models.URLField(_("Base URL"), blank=True)
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    is_default = models.BooleanField(
        _("Default Source"),
        default=False,
        help_text="True if this is an essential fallback source",
    )
    source_type = models.CharField(
        _("Source Type"),
        max_length=20,
        choices=[("web", "Web scraping"), ("api", "API")],
        default="web",
    )
    last_error = models.CharField(max_length=255, null=True, blank=True)
    last_error_at = models.DateTimeField(
        _("Last Error At"),
        null=True,
        blank=True,
    )
    last_failed_at = models.DateTimeField(
        _("Last Failed At"),
        null=True,
        blank=True,
    )
    fail_count = models.IntegerField(_("Fail Count"), default=0)
    consecutive_failures = models.IntegerField(default=0)
    last_failure_reason = models.CharField(max_length=200, blank=True, default="")
    last_failure_at = models.DateTimeField(null=True, blank=True)
    quarantine_reason = models.TextField(blank=True, default="")
    is_admin_disabled = models.BooleanField(default=False)
    fallback_url = models.URLField(_("Fallback URL"), blank=True, default="")
    last_scraped = models.DateTimeField(_("Last Scraped"), null=True, blank=True)
    scrape_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom CSS selectors or config",
    )
    css_selectors = models.JSONField(default=dict, blank=True)
    last_run_status = models.CharField(
        max_length=20,
        choices=[
            ("success", "Success"),
            ("partial", "Partial Success"),
            ("failed", "Failed"),
            ("pending", "Pending"),
        ],
        default="pending",
    )
    last_run_items_created = models.IntegerField(default=0)
    last_run_error = models.TextField(blank=True)
    use_rss = models.BooleanField(
        default=False,
        help_text="Try RSS/Atom feed detection first",
    )
    use_llm_extraction = models.BooleanField(
        default=True,
        help_text="Use LLM to extract structured data",
    )
    verify_ssl = models.BooleanField(
        default=True,
        help_text=(
            "Uncheck to disable SSL verification for this source "
            "(use for self-signed .dz university certificates)"
        ),
    )
    proxy_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Optional proxy URL for this source. "
            "Format: http://user:pass@host:port or socks5://host:port"
        ),
    )
    selector_recommendations = models.JSONField(null=True, blank=True)
    selector_confidence = models.FloatField(null=True, blank=True)
    schedule_tier = models.CharField(
        max_length=20,
        choices=[
            ("very_high", "Very High"),
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("dormant", "Dormant"),
        ],
        default="medium",
    )
    schedule_interval_hours = models.IntegerField(default=24)
    schedule_updated_at = models.DateTimeField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=10,
        choices=[
            ("GREEN", "OK"),
            ("YELLOW", "Avertissement"),
            ("RED", "Probleme"),
            ("PENDING", "En cours"),
            ("UNKNOWN", "Non teste"),
        ],
        default="UNKNOWN",
    )
    validation_detail = models.JSONField(null=True, blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = _("Scraping Source")
        verbose_name_plural = _("Scraping Sources")

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"  # type: ignore[attr-defined]

    def save(self, *args, **kwargs):
        # Keep legacy and new URL fields synchronized.
        if self.url and not self.base_url:
            self.base_url = self.url
        elif self.base_url and not self.url:
            self.url = self.base_url
        super().save(*args, **kwargs)


class SearchQuery(models.Model):
    """Configurable search query used by category scrapers."""

    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=SCRAPER_CATEGORY_CHOICES,
    )
    query_text = models.CharField(_("Query Text"), max_length=500)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        ordering = ["category", "id"]
        verbose_name = _("Search Query")
        verbose_name_plural = _("Search Queries")
        indexes = [
            models.Index(
                fields=["category", "is_active"], name="idx_searchquery_cat_active"
            )
        ]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"[{self.category}] {self.query_text[:80]} ({status})"


class DiscoveredURL(models.Model):
    """URLs discovered from event pages for future scraping runs."""

    DISCOVERY_METHOD_CHOICES = [
        ("css", _("CSS Selector")),
        ("llm", _("LLM Scan")),
        ("heuristic", _("Heuristic")),
    ]

    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=SCRAPER_CATEGORY_CHOICES,
        default="events",
        db_index=True,
    )
    url = models.URLField(_("URL"), unique=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        default="pending",
        db_index=True,
        choices=[
            ("pending", _("Pending")),
            ("completed", _("Completed")),
            ("failed", _("Failed")),
        ],
    )
    source_page_url = models.URLField(_("Source Page URL"), blank=True, default="")
    section_label = models.CharField(
        _("Section Label"), max_length=120, blank=True, default=""
    )
    discovery_method = models.CharField(
        _("Discovery Method"),
        max_length=20,
        choices=DISCOVERY_METHOD_CHOICES,
        default="heuristic",
    )
    keywords_hit = models.JSONField(_("Keywords Hit"), default=list, blank=True)
    priority_score = models.IntegerField(_("Priority Score"), default=0, db_index=True)
    times_seen = models.PositiveIntegerField(_("Times Seen"), default=1)
    is_processed = models.BooleanField(_("Is Processed"), default=False, db_index=True)
    first_discovered_at = models.DateTimeField(
        _("First Discovered At"), auto_now_add=True
    )
    last_discovered_at = models.DateTimeField(_("Last Discovered At"), auto_now=True)

    class Meta:
        db_table = "discovered_urls"
        ordering = ["-priority_score", "-times_seen", "-last_discovered_at"]
        verbose_name = _("Discovered URL")
        verbose_name_plural = _("Discovered URLs")
        indexes = [
            models.Index(
                fields=["category", "is_processed", "priority_score"],
                name="idx_discoveredurl_queue",
            ),
            models.Index(
                fields=["category", "status", "priority_score"],
                name="idx_discoveredurl_pending_queue",
            ),
        ]

    def __str__(self):
        return f"[{self.category}] {self.url}"


class RejectedItem(models.Model):
    """Feedback loop storage for rejected scraping candidates."""

    REASON_CHOICES = [
        ("irrelevant", _("Irrelevant to Arabic NLP")),
        ("poor_arabic", _("Poor Arabic translation")),
        ("duplicate", _("Duplicate content")),
        ("unreliable_source", _("Unreliable source")),
        ("outdated", _("Outdated information")),
        ("low_quality", _("Low quality content")),
        ("other", _("Other")),
    ]

    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=SCRAPER_CATEGORY_CHOICES,
    )
    title = models.CharField(_("Title"), max_length=300)
    reason_for_rejection = models.TextField(_("Reason For Rejection"))
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="scraping_rejected_items",
    )
    object_id = models.CharField(max_length=64, null=True, blank=True)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES, default="other")
    notes = models.TextField(blank=True, default="")
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scraping_rejections",
    )
    rejected_at = models.DateTimeField(_("Rejected At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        ordering = ["-rejected_at", "-created_at"]
        verbose_name = _("Rejected Item")
        verbose_name_plural = _("Rejected Items")
        indexes = [
            models.Index(
                fields=["category", "created_at"], name="idx_rejecteditem_cat_created"
            ),
            models.Index(
                fields=["category", "rejected_at"], name="idx_rejecteditem_cat_rejected"
            ),
        ]

    def __str__(self):
        return f"[{self.category}] {self.title[:80]} ({self.reason})"


class ScrapingRun(models.Model):
    """Log of each scraping execution."""

    STATUS_CHOICES = [
        ("running", _("Running")),
        ("completed", _("Completed")),
        ("failed", _("Failed")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(_("Category"), max_length=50)
    task_id = models.CharField(
        _("Celery Task ID"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Celery async task ID for status polling."),
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="running"
    )
    progress_current = models.IntegerField(_("Progress Current"), default=0)
    progress_total = models.IntegerField(_("Progress Total"), default=0)
    current_step = models.CharField(_("Current Step"), max_length=100, blank=True)
    current_message = models.CharField(_("Current Message"), max_length=255, blank=True)
    current_source = models.CharField(_("Current Source"), max_length=255, blank=True)
    current_item = models.CharField(_("Current Item"), max_length=255, blank=True)
    items_found = models.PositiveIntegerField(_("Items Found"), default=0)
    items_created = models.IntegerField(_("Items Created"), default=0)
    items_updated = models.PositiveIntegerField(_("Items Updated"), default=0)
    items_skipped = models.IntegerField(_("Items Skipped"), default=0)
    items_failed = models.IntegerField(_("Items Failed"), default=0)
    errors = models.TextField(_("Errors"), blank=True)
    started_at = models.DateTimeField(_("Started At"), auto_now_add=True)
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)
    triggered_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Triggered By"),
    )
    source = models.ForeignKey(
        "scraping.ScrapingSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scraping_runs",
        verbose_name=_("Source"),
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name = _("Scraping Run")
        verbose_name_plural = _("Scraping Runs")
        indexes = [
            models.Index(
                fields=["category", "-started_at"],
                name="idx_scrapingrun_cat_started",
            )
        ]

    def __str__(self):
        return f"{self.category} — {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ScrapingNotification(models.Model):
    """UI notifications for scraping admin shell (topbar dropdown)."""

    TYPE_CHOICES = [
        ("run_complete", _("Run Complete")),
        ("run_failed", _("Run Failed")),
        ("source_failing", _("Source Failing")),
        ("info", _("Info")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    category = models.CharField(max_length=50, blank=True, default="")
    message = models.CharField(max_length=500)
    run = models.ForeignKey(
        "scraping.ScrapingRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    source = models.ForeignKey(
        "scraping.ScrapingSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Scraping Notification")
        verbose_name_plural = _("Scraping Notifications")
        indexes = [
            models.Index(
                fields=["is_read", "created_at"], name="idx_scrapenotif_read_created"
            ),
            models.Index(
                fields=["notification_type", "created_at"],
                name="idx_scrapenotif_type_created",
            ),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.message[:72]}"


class ScrapingSourceHealth(models.Model):
    """Per-source health tracking with circuit breaker state.

    Each (category, source_name) pair gets one row that is updated
    after every scraping run.  The ``health_score`` decays on failures
    and recovers on success, while ``circuit_open`` flips once the
    score drops below the threshold.
    """

    CIRCUIT_CHOICES = [
        ("closed", _("Closed (healthy)")),
        ("open", _("Open (tripped)")),
        ("half_open", _("Half-Open (probing)")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(_("Category"), max_length=50)
    source_name = models.CharField(
        _("Source Name"),
        max_length=200,
        help_text=_("Logical name of the source (e.g. 'WikiCFP', 'HuggingFace Hub')."),
    )
    base_url = models.URLField(_("Base URL"), blank=True)

    # Counters
    total_attempts = models.PositiveIntegerField(_("Total Attempts"), default=0)
    total_successes = models.PositiveIntegerField(_("Total Successes"), default=0)
    total_failures = models.PositiveIntegerField(_("Total Failures"), default=0)
    consecutive_failures = models.PositiveIntegerField(
        _("Consecutive Failures"),
        default=0,
    )

    # Health
    health_score = models.FloatField(
        _("Health Score"),
        default=100.0,
        help_text=_("0-100. Decays on failure, recovers on success."),
    )

    # Circuit breaker
    circuit_state = models.CharField(
        _("Circuit State"),
        max_length=12,
        choices=CIRCUIT_CHOICES,
        default="closed",
    )
    circuit_opened_at = models.DateTimeField(
        _("Circuit Opened At"),
        null=True,
        blank=True,
    )
    circuit_cooldown_seconds = models.PositiveIntegerField(
        _("Cooldown (s)"),
        default=SS.CIRCUIT_COOLDOWN_SECONDS,
        help_text=_("Seconds before an open circuit moves to half-open."),
    )

    # Timing
    last_attempt_at = models.DateTimeField(_("Last Attempt"), null=True, blank=True)
    last_success_at = models.DateTimeField(_("Last Success"), null=True, blank=True)
    last_failure_at = models.DateTimeField(_("Last Failure"), null=True, blank=True)
    avg_response_time = models.FloatField(
        _("Avg Response Time (s)"),
        null=True,
        blank=True,
    )

    # Last error detail
    last_error = models.TextField(_("Last Error"), blank=True)

    class Meta:
        ordering = ["category", "source_name"]
        unique_together = [("category", "source_name")]
        verbose_name = _("Source Health")
        verbose_name_plural = _("Source Health Records")
        indexes = [
            models.Index(
                fields=["category", "source_name"],
                name="idx_sourcehealth_cat_source",
            )
        ]

    def __str__(self):
        return f"{self.source_name} ({self.category}) — {self.health_score:.0f}%"

    # ── Business logic ───────────────────────────────────────────────

    FAILURE_PENALTY = SS.FAILURE_PENALTY  # score points lost per failure
    SUCCESS_RECOVERY = SS.SUCCESS_RECOVERY  # score points gained per success
    CIRCUIT_THRESHOLD = SS.CIRCUIT_THRESHOLD  # score below which circuit opens
    CONSECUTIVE_TRIP = SS.CIRCUIT_TRIP_COUNT  # failures to trip circuit

    def _locked(self):
        return type(self).objects.select_for_update().get(pk=self.pk)

    def record_success(self, response_time: float | None = None):
        """Record a successful request to this source."""
        now = timezone.now()
        with transaction.atomic():
            locked = self._locked()
            updates = {
                "total_attempts": F("total_attempts") + 1,
                "total_successes": F("total_successes") + 1,
                "consecutive_failures": 0,
                "last_attempt_at": now,
                "last_success_at": now,
                "health_score": Least(
                    Value(100.0),
                    F("health_score") + Value(self.SUCCESS_RECOVERY),
                ),
            }

            if response_time is not None:
                if locked.avg_response_time is None:
                    updates["avg_response_time"] = response_time
                else:
                    # Exponential moving average
                    updates["avg_response_time"] = (
                        0.7 * locked.avg_response_time + 0.3 * response_time
                    )

            # Half-open probe succeeded -> close breaker
            if locked.circuit_state == "half_open":
                updates["circuit_state"] = "closed"
                updates["circuit_opened_at"] = None

            type(self).objects.filter(pk=self.pk).update(**updates)

        self.refresh_from_db()

    def record_failure(self, error: str = ""):
        """Record a failed request and evaluate circuit breaker."""
        now = timezone.now()
        with transaction.atomic():
            locked = self._locked()
            projected_health = max(0.0, locked.health_score - self.FAILURE_PENALTY)
            projected_failures = locked.consecutive_failures + 1

            updates = {
                "total_attempts": F("total_attempts") + 1,
                "total_failures": F("total_failures") + 1,
                "consecutive_failures": F("consecutive_failures") + 1,
                "last_attempt_at": now,
                "last_failure_at": now,
                "health_score": Greatest(
                    Value(0.0),
                    F("health_score") - Value(self.FAILURE_PENALTY),
                ),
            }
            if error:
                updates["last_error"] = error[:2000]

            # Closed breaker trips on threshold or consecutive failures
            if locked.circuit_state == "closed" and (
                projected_health < self.CIRCUIT_THRESHOLD
                or projected_failures >= self.CONSECUTIVE_TRIP
            ):
                updates["circuit_state"] = "open"
                updates["circuit_opened_at"] = now

            # Half-open probe failed -> reopen breaker
            if locked.circuit_state == "half_open":
                updates["circuit_state"] = "open"
                updates["circuit_opened_at"] = now

            type(self).objects.filter(pk=self.pk).update(**updates)

        self.refresh_from_db()

    def is_available(self) -> bool:
        """Check whether this source should be queried right now."""
        now = timezone.now()
        with transaction.atomic():
            locked = self._locked()

            if locked.circuit_state == "closed":
                return True

            if locked.circuit_state == "open":
                if locked.circuit_opened_at is None:
                    return False

                elapsed = (now - locked.circuit_opened_at).total_seconds()
                if elapsed < locked.circuit_cooldown_seconds:
                    return False

                # Cooldown passed: atomically move to half-open and claim probe.
                type(self).objects.filter(pk=self.pk).update(
                    circuit_state="half_open",
                    circuit_opened_at=now,
                    last_attempt_at=now,
                )
                self.refresh_from_db()
                return True

            # half_open: allow only one in-flight probe claim.
            half_open_since = locked.circuit_opened_at or now
            probe_already_claimed = (
                locked.last_attempt_at is not None
                and locked.last_attempt_at >= half_open_since
            )
            if probe_already_claimed:
                return False

            type(self).objects.filter(pk=self.pk).update(
                circuit_opened_at=half_open_since,
                last_attempt_at=now,
            )
            self.refresh_from_db()
            return True


class ScrapedItemMeta(models.Model):
    """Per-item intelligence metadata: domain classification, relevance score.

    Stores Phase 6 intelligence data for any scraped item, linked by
    content_type + object_id (generic FK pattern) or simply by
    category + item_title for lightweight lookups.
    """

    SKIP_REASON_CHOICES = [
        (SKIP_DEDUP_URL, "Dedup URL"),
        (SKIP_DEDUP_NAME, "Dedup Name"),
        (SKIP_DEDUP_SIMILARITY, "Dedup Similarity"),
        (SKIP_DEDUP_EMBEDDING, "Dedup Embedding"),
        (SKIP_DEDUP_DOI, "Dedup DOI"),
        (SKIP_DEDUP_ARXIV, "Dedup arXiv"),
        (SKIP_DEDUP_ROR, "Dedup ROR"),
        (SKIP_DOWNLOAD_FAIL, "Download Failed"),
        (SKIP_VALIDATION_FAIL, "Validation Failed"),
        (SKIP_ENRICHMENT_FAIL, "Enrichment Failed"),
        (SKIP_CIRCUIT_OPEN, "Circuit Open"),
    ]

    TRANSLATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("missing", "Missing"),
        ("translated", "Translated"),
        ("copied", "Copied"),
        ("failed", "Failed"),
        ("partial", "Partial"),
    ]

    source_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Human label of source e.g. WikiCFP, arXiv cs.CL",
    )
    source_url = models.URLField(
        max_length=2000,
        null=True,
        blank=True,
        help_text="Canonical URL of the source page or feed",
    )
    content_source = models.CharField(
        max_length=20,
        choices=[
            ("live", "Live"),
            ("wayback", "Wayback Machine"),
            ("cache", "Cache"),
        ],
        default="live",
    )
    archived_snapshot_url = models.URLField(null=True, blank=True)
    match_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Similarity score when item was dedup-skipped (0.0-1.0)",
    )
    matched_item_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID of the existing DB item this was matched against",
    )
    download_result = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="DownloadResult code for the media download attempt",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(_("Category"), max_length=50)
    item_title = models.CharField(_("Item Title"), max_length=300)
    item_id = models.CharField(
        _("Item UUID"),
        max_length=50,
        blank=True,
        default="",
        help_text=_("UUID of the scraped item in its source table."),
    )
    skip_reason = models.CharField(
        _("Skip Reason"),
        max_length=32,
        choices=SKIP_REASON_CHOICES,
        null=True,
        blank=True,
        help_text=_("Reason why this scraped candidate was skipped as duplicate."),
    )
    was_skipped = models.BooleanField(
        _("Was Skipped"),
        default=False,
        help_text=_("Whether this candidate was skipped in ingestion."),
    )

    # Domain classification (JSON: {"arabic_nlp": 0.85, "llm_research": 0.6})
    domain_scores = models.JSONField(
        _("Domain Scores"),
        default=dict,
        blank=True,
        help_text=_("Dict of domain_key → confidence (0-1)."),
    )
    primary_domain = models.CharField(
        _("Primary Domain"),
        max_length=50,
        blank=True,
        default="general",
    )

    # Relevance score (0-100)
    relevance_score = models.FloatField(
        _("Relevance Score"),
        default=0.0,
        help_text=_(
            "Composite score 0-100 combining recency, relevance, health, popularity."
        ),
    )
    enrichment_status = models.CharField(
        _("Enrichment Status"),
        max_length=20,
        choices=[
            ("not_enriched", "Not Enriched"),
            ("partial", "Partial"),
            ("complete", "Complete"),
        ],
        default="not_enriched",
        help_text=_("Whether deep enrichment fully succeeded for this item."),
    )
    translation_status = models.CharField(
        _("Translation Status"),
        max_length=12,
        choices=TRANSLATION_STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text=_("Arabic translation pipeline status for this item."),
    )
    completeness_score = models.FloatField(
        default=0.0,
        help_text="Percentage of fields filled (0-100)",
    )

    # Semantic embedding for duplicate detection (384-d MiniLM).
    # In SQLite test mode we store this as JSON to avoid Postgres/pgvector coupling.
    if _vector_field_enabled():
        title_embedding = VectorField(
            dimensions=DEDUP_EMBEDDING_DIM,
            null=True,
            blank=True,
            help_text=_(
                f"{DEDUP_EMBEDDING_DIM}-dim embedding from {DEDUP_EMBEDDING_MODEL}."
            ),
        )
    else:
        title_embedding = models.JSONField(
            null=True,
            blank=True,
            default=None,
            help_text=_("Embedding payload for non-PostgreSQL test environments."),
        )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-relevance_score"]
        verbose_name = _("Scraped Item Metadata")
        verbose_name_plural = _("Scraped Item Metadata")
        indexes = [
            models.Index(fields=["category", "primary_domain"]),
            models.Index(fields=["-relevance_score"]),
            models.Index(
                fields=["category", "source_name"], name="idx_scraped_cat_source"
            ),
            models.Index(
                fields=["category", "skip_reason", "created_at"],
                name="idx_scraped_cat_skip_created",
            ),
        ]

    def __str__(self):
        return f"{self.item_title[:60]} — {self.primary_domain} ({self.relevance_score:.0f})"

    def save(self, *args, **kwargs):
        previous_reason = None
        previous_was_skipped = False
        if self.pk:
            existing = (
                type(self)
                .objects.filter(pk=self.pk)
                .only("skip_reason", "was_skipped")
                .first()
            )
            if existing is not None:
                previous_reason = existing.skip_reason
                previous_was_skipped = bool(existing.was_skipped)

        super().save(*args, **kwargs)

        reason = (self.skip_reason or "").strip()
        if (
            self.was_skipped
            and reason
            and (reason != (previous_reason or "") or not previous_was_skipped)
        ):
            try:
                from scraping.metrics import record_skip_reason

                record_skip_reason(self.category, reason)
            except (ImportError, DatabaseError, ValueError, TypeError) as exc:
                # Metrics emission must not break persistence.
                logger.error(
                    "scraped_item_meta_metrics_emit_failed",
                    extra={
                        "error": str(exc),
                        "context": str(self.pk),
                    },
                    exc_info=False,
                )
