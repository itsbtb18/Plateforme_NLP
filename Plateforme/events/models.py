import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from institutions.models import Institution


class EventSoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def delete(self):
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class ActiveEventManager(models.Manager.from_queryset(EventSoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllEventManager(models.Manager.from_queryset(EventSoftDeleteQuerySet)):
    pass


class Event(models.Model):
    """Model for scientific events related to Arabic NLP research."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    TYPE_CHOICES = (
        ("conference", _("Conference")),
        ("workshop", _("Workshop")),
        ("seminar", _("Seminar")),
        ("call_for_papers", _("Call for Papers")),
        ("hackathon", _("Hackathon")),
        ("other", _("Other")),
    )

    DOMAIN_CHOICES = (
        ("nlp", _("Natural Language Processing")),
        ("speech", _("Speech Processing")),
        ("ai", _("Artificial Intelligence")),
        ("arabic_lang", _("Arabic Language")),
        ("linguistics", _("Linguistics")),
        ("machine_translation", _("Machine Translation")),
        ("sentiment_analysis", _("Sentiment Analysis")),
        ("text_summarization", _("Text Summarization")),
        ("other", _("Other")),
    )

    LANGUAGE_CHOICES = (
        ("ar", _("Arabic")),
        ("fr", _("French")),
        ("en", _("English")),
        ("other", _("Other")),
    )

    APPROVAL_STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    )

    SCRAPE_STATUS_APPROVED = "APPROVED"
    SCRAPE_STATUS_PENDING_REVIEW = "PENDING_REVIEW"
    SCRAPE_STATUS_REJECTED = "REJECTED"
    SCRAPE_STATUS_CHOICES = (
        (SCRAPE_STATUS_APPROVED, _("Approved")),
        (SCRAPE_STATUS_PENDING_REVIEW, _("Pending review")),
        (SCRAPE_STATUS_REJECTED, _("Rejected")),
    )

    source = models.CharField(
        max_length=100,
        blank=True,
        default="manual",
        help_text="Source of this event record: manual, scraped, custom_scrape, etc.",
    )

    title = models.CharField(_("Title"), max_length=255)
    title_ar = models.CharField(
        _("Title (Arabic)"), max_length=255, blank=True, default=""
    )
    title_en = models.CharField(
        _("Title (English)"), max_length=255, blank=True, default=""
    )
    description = models.TextField(_("Description"))
    description_ar = models.TextField(_("Description (Arabic)"), blank=True, default="")
    description_en = models.TextField(
        _("Description (English)"), blank=True, default=""
    )
    event_type = models.CharField(_("Event Type"), max_length=20, choices=TYPE_CHOICES)
    domains = models.CharField(
        _("Domains"), max_length=255, help_text=_("Comma-separated domains")
    )
    location = models.CharField(
        _("Location"),
        max_length=255,
        blank=True,
        help_text=_("Leave blank for virtual events"),
    )
    location_ar = models.CharField(
        _("Location (Arabic)"), max_length=255, blank=True, default=""
    )
    location_en = models.CharField(
        _("Location (English)"), max_length=255, blank=True, default=""
    )
    is_approved = models.BooleanField(_("Approved"), default=False)
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending",
    )
    scrape_status = models.CharField(
        _("Scrape Status"),
        max_length=20,
        choices=SCRAPE_STATUS_CHOICES,
        default=SCRAPE_STATUS_PENDING_REVIEW,
        db_index=True,
    )
    validation_notes = models.TextField(_("Validation Notes"), blank=True, default="")
    confidence_score = models.FloatField(
        _("Confidence Score"),
        null=True,
        blank=True,
        db_index=True,
    )
    approval_date = models.DateTimeField(_("Approval Date"), null=True, blank=True)
    approved_by = models.ForeignKey(
        get_user_model(),
        related_name="approved_events",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Approved By"),
    )
    rejection_reason = models.TextField(_("Rejection Reason"), blank=True, default="")
    view_count = models.IntegerField(
        _("View Count"), default=0, validators=[MinValueValidator(0)]
    )
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    submission_deadline = models.DateField(
        _("Submission Deadline"), null=True, blank=True
    )
    notification_date = models.DateField(_("Notification Date"), null=True, blank=True)
    website = models.URLField(_("Website"), blank=True, db_index=True)
    registration_link = models.URLField(_("Registration Link"), null=True, blank=True)
    is_online = models.BooleanField(_("Is Online"), default=False)
    is_hybrid = models.BooleanField(_("Is Hybrid"), default=False)
    source_url = models.URLField(_("Source URL"), null=True, blank=True)
    source_name = models.CharField(
        _("Source Name"), max_length=120, null=True, blank=True
    )
    last_scraped_at = models.DateTimeField(
        _("Last Scraped At"), null=True, blank=True, db_index=True
    )
    update_count = models.PositiveIntegerField(_("Update Count"), default=0)
    update_counter = models.PositiveIntegerField(_("Update Counter"), default=0)
    is_past_event = models.BooleanField(
        _("Is Past Event"), default=False, db_index=True
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="en",
    )
    tags = models.JSONField(_("Tags"), null=True, blank=True)
    entities = models.JSONField(_("Entities"), blank=True, default=dict)
    organizer = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        verbose_name=_("Organizer"),
        related_name="events",
    )
    contact_email = models.EmailField(_("Contact Email"))

    # File attachments for call for papers, etc.
    attachment = models.FileField(
        _("Attachment"),
        upload_to="event_attachments/",
        blank=True,
        null=True,
        help_text=_("Supported formats: PDF, DOC/DOCX, PPT/PPTX (Max 5MB)"),
    )
    banner_image = models.ImageField(
        _("Banner Image"),
        upload_to="events/banners/",
        blank=True,
        null=True,
    )

    # Metadata
    created_by = models.ForeignKey(
        get_user_model(), related_name="created_events", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        get_user_model(),
        related_name="deleted_events_set",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    objects = ActiveEventManager()
    all_objects = AllEventManager()

    class Meta:
        ordering = ["-start_date"]
        verbose_name = _("Event")
        verbose_name_plural = _("Events")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("events:event_detail", kwargs={"pk": self.pk})

    def get_localized_title(self):
        """Return title based on current language"""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.title_ar:
            return self.title_ar
        elif self.title_en:
            return self.title_en
        return self.title

    def get_localized_description(self):
        """Return description based on current language"""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.description_ar:
            return self.description_ar
        elif self.description_en:
            return self.description_en
        return self.description

    def get_localized_location(self):
        """Return location based on current language with fallback"""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.location_ar:
            return self.location_ar
        elif self.location_en:
            return self.location_en
        return self.location

    @property
    def title_display(self):
        """Return title based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.title_ar or ""
        return self.title_en or ""

    @property
    def description_display(self):
        """Return description based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.description_ar or ""
        return self.description_en or ""

    @property
    def location_display(self):
        """Return location based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.location_ar or ""
        return self.location_en or ""

    @property
    def is_virtual(self):
        """Determine if the event is virtual based on location field."""
        return not bool(self.location.strip())

    @property
    def is_upcoming(self):
        return self.start_date > timezone.now().date()

    @property
    def is_ongoing(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def is_past(self):
        return self.end_date < timezone.now().date()

    @property
    def days_until_deadline(self):
        if not self.submission_deadline:
            return None

        delta = self.submission_deadline - timezone.now().date()
        return delta.days if delta.days >= 0 else None

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user and getattr(user, "is_authenticated", False):
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def hard_delete(self):
        super().delete()

    @property
    def domain_list(self):
        if not self.domains:
            return []
        return [domain.strip() for domain in self.domains.split(",")]

    def clean(self):
        """Validate model data."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(_("End date must be after start date"))

        if (
            self.submission_deadline
            and self.start_date
            and self.submission_deadline > self.start_date
        ):
            raise ValidationError(
                _("Submission deadline must be before event start date")
            )


class EventRegistration(models.Model):
    """Model to track users who registered for events."""

    event = models.ForeignKey(
        Event, related_name="registrations", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        get_user_model(), related_name="event_registrations", on_delete=models.CASCADE
    )
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        verbose_name = _("Event Registration")
        verbose_name_plural = _("Event Registrations")

    def __str__(self):
        return f"{self.user.email} - {self.event.title}"


class Speaker(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        related_name="speakers",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    affiliation = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    talk_title = models.CharField(max_length=255, blank=True)
    talk_abstract = models.TextField(blank=True)
    website = models.URLField(blank=True)
    avatar = models.ImageField(upload_to="events/speakers/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("Speaker")
        verbose_name_plural = _("Speakers")

    def __str__(self):
        return f"{self.name} ({self.event.title})"
