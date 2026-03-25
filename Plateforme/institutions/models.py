import uuid
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.conf import settings


class Country(models.Model):
    name_en = models.CharField(_("Country Name (English)"), max_length=100)
    name_ar = models.CharField(_("Country Name (Arabic)"), max_length=100)
    code = models.CharField(_("Country Code"), max_length=2, unique=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["name_en"]

    def __str__(self):
        from django.utils.translation import get_language

        current_lang = get_language()
        return self.name_ar if current_lang == "ar" else self.name_en

    def get_localized_name(self):
        """Return name based on current language."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.name_ar:
            return self.name_ar
        return self.name_en


class Specialty(models.Model):
    name_en = models.CharField(
        _("Specialty Name (English)"), max_length=100, unique=True, default=""
    )
    name_ar = models.CharField(
        _("Specialty Name (Arabic)"), max_length=100, blank=True, default=""
    )
    code = models.CharField(_("Specialty Code"), max_length=20, unique=True)

    class Meta:
        verbose_name = _("Specialty")
        verbose_name_plural = _("Specialties")
        ordering = ["name_en"]

    def __str__(self):
        from django.utils.translation import get_language

        current_lang = get_language()
        return self.name_ar if current_lang == "ar" else self.name_en

    def get_localized_name(self):
        """Return name based on current language."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.name_ar:
            return self.name_ar
        return self.name_en


class Institution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    TYPE = [
        ("School", _("School")),
        ("University", _("University")),
        ("Research Center", _("Research Center")),
        ("Other", _("Other")),
    ]
    name = models.CharField(_("Institution Name"), max_length=255)
    name_ar = models.CharField(
        _("Institution Name (Arabic)"), max_length=255, blank=True, default=""
    )
    name_en = models.CharField(
        _("Institution Name (English)"), max_length=255, blank=True, default=""
    )
    acronym = models.CharField(_("Acronym"), max_length=20, blank=True)
    ror_id = models.CharField(
        _("ROR ID"), max_length=100, blank=True, default="", db_index=True
    )
    founding_year = models.IntegerField(_("Founding Year"), null=True, blank=True)
    director = models.CharField(_("Director"), max_length=255, null=True, blank=True)
    affiliated_researchers_count = models.IntegerField(
        _("Affiliated Researchers Count"),
        null=True,
        blank=True,
    )
    notable_publications = models.JSONField(
        _("Notable Publications"),
        null=True,
        blank=True,
    )
    social_links = models.JSONField(_("Social Links"), null=True, blank=True)
    source_url = models.URLField(_("Source URL"), null=True, blank=True)
    source_name = models.CharField(
        _("Source Name"),
        max_length=120,
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=255, choices=TYPE)
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, verbose_name=_("Country")
    )
    city = models.CharField(_("City"), max_length=100)
    city_ar = models.CharField(
        _("City (Arabic)"), max_length=100, blank=True, default=""
    )
    city_en = models.CharField(
        _("City (English)"), max_length=100, blank=True, default=""
    )
    specialties = models.ManyToManyField(Specialty, verbose_name=_("Specialties"))

    logo = models.ImageField(
        _("Logo"), upload_to="institutions/logos/", blank=True, null=True
    )

    website = models.URLField(_("Website"), blank=True, db_index=True)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Phone"), max_length=50, blank=True)
    address = models.TextField(_("Address"), blank=True)
    address_ar = models.TextField(_("Address (Arabic)"), blank=True, default="")
    address_en = models.TextField(_("Address (English)"), blank=True, default="")
    # Legacy field - kept for compatibility
    description = models.TextField(_("Description"), blank=True)
    # Bilingual description fields
    description_ar = models.TextField(_("Description (Arabic)"), blank=True)
    description_en = models.TextField(_("Description (English)"), blank=True)

    image = models.ImageField(default="default.jpg", upload_to="institution_pics")

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    # Use AUTH_USER_MODEL here:
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name=_("Created By"),
        related_name="created_institutions",
        null=True,
        blank=True,
    )

    APPROVAL_STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending",
        verbose_name=_("Approval Status"),
        help_text=_(
            "Institution must be approved by admin before being publicly visible"
        ),
    )

    class Meta:
        verbose_name = _("Institution")
        verbose_name_plural = _("Institutions")
        ordering = ["name"]

    @property
    def name_display(self):
        """Return name based on current language - NO fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.name_ar or ""
        return self.name_en or ""

    @property
    def description_display(self):
        """Return description based on current language - NO fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return getattr(self, "description_ar", "") or ""
        return getattr(self, "description_en", "") or ""

    def get_localized_name(self):
        """Return name based on current language with fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.name_ar:
            return self.name_ar
        elif self.name_en:
            return self.name_en
        return self.name

    def get_localized_description(self):
        """Return description based on current language with fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.description_ar:
            return self.description_ar
        elif self.description_en:
            return self.description_en
        return self.description

    def get_localized_city(self):
        """Return city based on current language with fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.city_ar:
            return self.city_ar
        elif self.city_en:
            return self.city_en
        return self.city

    def get_localized_address(self):
        """Return address based on current language with fallback."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar") and self.address_ar:
            return self.address_ar
        elif self.address_en:
            return self.address_en
        return self.address

    def __str__(self):
        from django.utils.translation import get_language

        current_lang = get_language()
        if current_lang == "ar" and self.name_ar:
            return self.name_ar
        elif self.name_en:
            return self.name_en
        return self.name

    def get_absolute_url(self):
        return reverse("institutions:institution_detail", kwargs={"pk": self.pk})
