import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _


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
