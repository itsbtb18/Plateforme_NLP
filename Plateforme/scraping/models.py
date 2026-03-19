import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from pgvector.django import VectorField


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

    def __str__(self):
        return f"{self.source_name} ({self.category}) — {self.health_score:.0f}%"

    # ── Business logic ───────────────────────────────────────────────

    FAILURE_PENALTY = 15.0  # score points lost per failure
    SUCCESS_RECOVERY = 10.0  # score points gained per success
    CIRCUIT_THRESHOLD = 25.0  # score below which circuit opens
    CONSECUTIVE_TRIP = 3  # consecutive failures to trip circuit

    def record_success(self, response_time: float | None = None):
        """Record a successful request to this source."""
        now = timezone.now()
        self.total_attempts += 1
        self.total_successes += 1
        self.consecutive_failures = 0
        self.last_attempt_at = now
        self.last_success_at = now
        self.health_score = min(100.0, self.health_score + self.SUCCESS_RECOVERY)

        if response_time is not None:
            if self.avg_response_time is None:
                self.avg_response_time = response_time
            else:
                # Exponential moving average
                self.avg_response_time = (
                    0.7 * self.avg_response_time + 0.3 * response_time
                )

        # Close circuit if it was half-open
        if self.circuit_state == "half_open":
            self.circuit_state = "closed"
            self.circuit_opened_at = None

        self.save()

    def record_failure(self, error: str = ""):
        """Record a failed request and evaluate circuit breaker."""
        now = timezone.now()
        self.total_attempts += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_attempt_at = now
        self.last_failure_at = now
        self.health_score = max(0.0, self.health_score - self.FAILURE_PENALTY)
        if error:
            self.last_error = error[:2000]

        # Trip the circuit breaker
        if self.circuit_state == "closed" and (
            self.health_score < self.CIRCUIT_THRESHOLD
            or self.consecutive_failures >= self.CONSECUTIVE_TRIP
        ):
            self.circuit_state = "open"
            self.circuit_opened_at = now

        # Half-open probe failed → re-open
        if self.circuit_state == "half_open":
            self.circuit_state = "open"
            self.circuit_opened_at = now

        self.save()

    def is_available(self) -> bool:
        """Check whether this source should be queried right now."""
        if self.circuit_state == "closed":
            return True

        if self.circuit_state == "open" and self.circuit_opened_at:
            elapsed = (timezone.now() - self.circuit_opened_at).total_seconds()
            if elapsed >= self.circuit_cooldown_seconds:
                # Transition to half-open for one probe attempt
                self.circuit_state = "half_open"
                self.save(update_fields=["circuit_state"])
                return True
            return False

        # half_open — allow exactly one probe
        return self.circuit_state == "half_open"


class ScrapedItemMeta(models.Model):
    """Per-item intelligence metadata: domain classification, relevance score.

    Stores Phase 6 intelligence data for any scraped item, linked by
    content_type + object_id (generic FK pattern) or simply by
    category + item_title for lightweight lookups.
    """

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
    completeness_score = models.FloatField(
        default=0.0,
        help_text="Percentage of fields filled (0-100)",
    )

    # Semantic embedding for duplicate detection (384-d MiniLM)
    title_embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text=_("384-dim embedding from paraphrase-multilingual-MiniLM-L12-v2."),
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
        ]

    def __str__(self):
        return f"{self.item_title[:60]} — {self.primary_domain} ({self.relevance_score:.0f})"
