import logging
import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, models, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest, Least
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

try:
    from pgvector.django import VectorField
except Exception:  # pragma: no cover - optional dependency at runtime
    VectorField = None

CIRCUIT_THRESHOLD = float(os.environ.get("SCRAPING_CIRCUIT_THRESHOLD", 25.0))
CONSECUTIVE_TRIP = int(os.environ.get("SCRAPING_CIRCUIT_TRIP_COUNT", 3))

logger = logging.getLogger(__name__)


def _vector_field_enabled() -> bool:
    if VectorField is None:
        return False

    if getattr(settings, "SCRAPING_DISABLE_VECTOR_FIELD", False):
        return False

    engine = str(settings.DATABASES.get("default", {}).get("ENGINE", ""))
    return "postgresql" in engine


class ScrapingSource(models.Model):
    """Configurable scraping source definition."""

    CATEGORY_CHOICES = [
        ("events", _("Events")),
        ("tools", _("Tools")),
        ("news", _("News")),
        ("courses", _("Courses")),
        ("institutions", _("Institutions")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Source Name"), max_length=200)
    category = models.CharField(_("Category"), max_length=50, choices=CATEGORY_CHOICES)
    base_url = models.URLField(_("Base URL"), blank=True)
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    last_scraped = models.DateTimeField(_("Last Scraped"), null=True, blank=True)
    scrape_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom CSS selectors or config",
    )
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = _("Scraping Source")
        verbose_name_plural = _("Scraping Sources")

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"  # type: ignore[attr-defined]


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
    items_found = models.PositiveIntegerField(_("Items Found"), default=0)
    items_created = models.PositiveIntegerField(_("Items Created"), default=0)
    items_skipped = models.PositiveIntegerField(_("Items Skipped"), default=0)
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
        default=300,
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

    FAILURE_PENALTY = 15.0  # score points lost per failure
    SUCCESS_RECOVERY = 10.0  # score points gained per success
    CIRCUIT_THRESHOLD = CIRCUIT_THRESHOLD  # score below which circuit opens
    CONSECUTIVE_TRIP = CONSECUTIVE_TRIP  # consecutive failures to trip circuit

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
        ("dedup_url", "Dedup URL"),
        ("dedup_name", "Dedup Name"),
        ("dedup_similarity", "Dedup Similarity"),
        ("dedup_embedding", "Dedup Embedding"),
        ("dedup_doi", "Dedup DOI"),
        ("dedup_arxiv", "Dedup arXiv"),
        ("dedup_ror", "Dedup ROR"),
        ("download_fail", "Download Failed"),
        ("validation_fail", "Validation Failed"),
        ("enrichment_fail", "Enrichment Failed"),
        ("circuit_open", "Circuit Open"),
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
    completeness_score = models.FloatField(
        default=0.0,
        help_text="Percentage of fields filled (0-100)",
    )

    # Semantic embedding for duplicate detection (384-d MiniLM).
    # In SQLite test mode we store this as JSON to avoid Postgres/pgvector coupling.
    if _vector_field_enabled():
        title_embedding = VectorField(
            dimensions=384,
            null=True,
            blank=True,
            help_text=_(
                "384-dim embedding from paraphrase-multilingual-MiniLM-L12-v2."
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
