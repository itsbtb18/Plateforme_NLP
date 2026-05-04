import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from institutions.models import Institution

from .managers import CustomUserManager


class CustomUser(AbstractUser):
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("active", _("Active")),
        ("blocked", _("Blocked")),
    ]

    SPECIALITY_CHOICES = [
        ("machine_learning", _("Machine Learning")),
        ("deep_learning", _("Deep Learning")),
        ("nlp", _("Natural Language Processing (NLP)")),
        ("computer_vision", _("Computer Vision")),
        ("reinforcement_learning", _("Reinforcement Learning")),
        ("ai_ethics", _("AI Ethics")),
        ("robotics", _("Robotics and AI")),
        ("neural_networks", _("Neural Networks")),
        ("ai_security", _("AI Security")),
        ("ai_healthcare", _("AI in Healthcare")),
        ("ai_finance", _("AI in Finance")),
        ("ai_education", _("AI in Education")),
        ("ai_transport", _("AI in Transportation")),
        ("ai_agriculture", _("AI in Agriculture")),
        ("ai_energy", _("AI in Energy")),
        ("ai_manufacturing", _("AI in Manufacturing")),
        ("ai_research", _("Fundamental AI Research")),
        ("autre", _("Other AI Field")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("full name")
    )
    full_name_ar = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Full Name (Arabic)"),
        help_text=_("Full name in Arabic"),
    )
    full_name_en = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Full Name (English)"),
        help_text=_("Full name in English"),
    )
    bio = models.TextField(blank=True, verbose_name=_("biography"))
    bio_ar = models.TextField(
        blank=True, default="", verbose_name=_("Biography (Arabic)")
    )
    bio_en = models.TextField(
        blank=True, default="", verbose_name=_("Biography (English)")
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("institution"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name=_("status"),
    )
    avatar = models.ImageField(
        upload_to="avatars/%Y/%m/%d/",
        null=True,
        blank=True,
        verbose_name=_("profile picture"),
    )
    is_email_verified = models.BooleanField(
        default=False, verbose_name=_("email verified")
    )
    email_verification_code = models.CharField(
        max_length=6, blank=True, null=True, verbose_name=_("email verification code")
    )
    speciality = models.CharField(
        max_length=100,
        choices=SPECIALITY_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("field of specialization in AI"),
    )
    linkedin_url = models.URLField(
        max_length=200, blank=True, null=True, verbose_name=_("LinkedIn URL")
    )
    twitter_url = models.URLField(
        max_length=200, blank=True, null=True, verbose_name=_("Twitter URL")
    )
    facebook_url = models.URLField(
        max_length=200, blank=True, null=True, verbose_name=_("Facebook URL")
    )
    is_verified = models.BooleanField(default=False, verbose_name=_("verified"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    show_online_status = models.BooleanField(
        default=True, verbose_name=_("show online status")
    )

    objects: CustomUserManager = CustomUserManager()  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name_en", "full_name_ar"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def generate_verification_code(self):
        self.email_verification_code = get_random_string(
            length=6, allowed_chars="0123456789"
        )
        self.save()

    def get_localized_full_name(self):
        """Return full name based on current language"""
        from django.utils.translation import get_language

        lang = get_language()
        if lang == "ar" and self.full_name_ar:
            return self.full_name_ar
        elif self.full_name_en:
            return self.full_name_en
        return self.full_name or self.email

    @property
    def get_full_name_display(self):
        """
        Smart full name property for templates - WITH fallback for user display.

        Returns the full name in the current language with fallback:
        - If Arabic language is active: returns full_name_ar (fallback to full_name_en)
        - If English language is active: returns full_name_en (fallback to full_name_ar)
        - Final fallback: full_name or email
        """
        from django.utils.translation import get_language

        lang = get_language()

        if lang and lang.startswith("ar"):
            # Arabic language: prefer Arabic, fallback to English
            if self.full_name_ar:
                return self.full_name_ar
            elif self.full_name_en:
                return self.full_name_en
        else:
            # English or other: prefer English, fallback to Arabic
            if self.full_name_en:
                return self.full_name_en
            elif self.full_name_ar:
                return self.full_name_ar

        # Final fallback
        return self.full_name or self.email

    @property
    def full_name_display(self):
        """Return full name based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.full_name_ar or ""
        return self.full_name_en or ""

    @property
    def bio_display(self):
        """Return bio based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language

        lang = get_language()
        if lang and lang.startswith("ar"):
            return self.bio_ar or ""
        return self.bio_en or ""

    def get_localized_bio(self):
        """Return bio based on current language"""
        from django.utils.translation import get_language

        lang = get_language()
        if lang == "ar" and self.bio_ar:
            return self.bio_ar
        elif self.bio_en:
            return self.bio_en
        return self.bio

    def clean(self):
        """Validate model fields."""
        super().clean()

        # Normalize email to lowercase
        if self.email:
            self.email = self.email.lower().strip()

        # Validate social URLs format
        url_validator = URLValidator()
        social_fields = ["linkedin_url", "twitter_url", "facebook_url"]

        for field_name in social_fields:
            url = getattr(self, field_name, None)
            if url:
                try:
                    url_validator(url)
                except ValidationError:
                    raise ValidationError({field_name: _("Enter a valid URL.")})

        # Validate LinkedIn URL format
        if self.linkedin_url and "linkedin.com" not in self.linkedin_url.lower():
            raise ValidationError(
                {"linkedin_url": _("Please enter a valid LinkedIn URL.")}
            )

        # Validate Twitter URL format
        if self.twitter_url:
            twitter_lower = self.twitter_url.lower()
            if "twitter.com" not in twitter_lower and "x.com" not in twitter_lower:
                raise ValidationError(
                    {"twitter_url": _("Please enter a valid Twitter/X URL.")}
                )

    def save(self, *args, **kwargs):
        """Override save to ensure email is normalized."""
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def get_short_name(self):
        """Return the short name for the user."""
        if self.full_name_en:
            return self.full_name_en.split()[0]
        elif self.full_name_ar:
            return self.full_name_ar.split()[0]
        return self.email.split("@")[0]

    def get_initials(self):
        """Return user initials for avatar placeholder."""
        name = self.get_full_name_display
        if name and name != self.email:
            parts = name.split()
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            return name[0].upper()
        return self.email[0].upper()

    def is_profile_complete(self):
        """Check if user has completed their profile."""
        required_fields = [
            self.full_name_en or self.full_name_ar,
            self.speciality,
        ]
        return all(required_fields)

    @property
    def display_status(self):
        """Return localized status display."""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def display_speciality(self):
        """Return localized speciality display."""
        if self.speciality:
            return dict(self.SPECIALITY_CHOICES).get(self.speciality, self.speciality)
        return None

    def __str__(self):
        """Return string representation with name if available."""
        name = self.get_full_name_display
        if name and name != self.email:
            return f"{name} ({self.email})"
        return self.email

    def __repr__(self):
        """Return developer-friendly representation."""
        return f"<CustomUser: {self.email} (id={self.id})>"


class UserProfile(models.Model):
    """
    Extended profile information linked to the auth user model.
    """

    orcid_validator = RegexValidator(
        regex=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$",
        message=_("ORCID must be in the format 0000-0000-0000-0000."),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    bio = models.TextField(blank=True, default="")
    orcid = models.CharField(
        max_length=19,
        blank=True,
        null=True,
        validators=[orcid_validator],
    )
    github_username = models.CharField(max_length=39, blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )
    is_independent = models.BooleanField(default=False)
    expertise_tags = models.ManyToManyField(
        "taxonomy.ResearchDomain",
        blank=True,
        related_name="user_profiles",
    )
    country = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(
        upload_to="profiles/avatars/%Y/%m/%d/",
        blank=True,
        null=True,
    )
    show_online_status = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    def __str__(self):
        return f"Profile for {self.get_display_name()}"

    def get_display_name(self) -> str:
        full_name = ""
        if hasattr(self.user, "get_full_name"):
            full_name = (self.user.get_full_name() or "").strip()
        if full_name:
            return full_name

        username = getattr(self.user, "username", "")
        if username:
            return str(username)

        return str(getattr(self.user, "email", "user"))


class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Friends")
        BLOCKED = "blocked", _("Blocked")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_sent",
    )
    addressee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_received",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("requester", "addressee")
        indexes = [
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["addressee", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.requester_id == self.addressee_id:
            raise ValidationError(_("You cannot create a relationship with yourself."))

    def __str__(self):
        return f"{self.requester_id} -> {self.addressee_id} ({self.status})"

    @staticmethod
    def between(user_a, user_b):
        if not user_a or not user_b or user_a == user_b:
            return None
        return Friendship.objects.filter(
            models.Q(requester=user_a, addressee=user_b)
            | models.Q(requester=user_b, addressee=user_a)
        ).first()

    @staticmethod
    def relation_state(viewer, profile_user):
        """
        Returns one of:
        NEUTRE, EN_ATTENTE_ENVOYE, EN_ATTENTE_RECU, AMIS, BLOQUE
        """
        if not viewer or not profile_user or viewer == profile_user:
            return "NEUTRE"
        rel = Friendship.between(viewer, profile_user)
        if not rel:
            return "NEUTRE"
        if rel.status == Friendship.Status.BLOCKED:
            return "BLOQUE"
        if rel.status == Friendship.Status.ACCEPTED:
            return "AMIS"
        if rel.requester_id == viewer.id:
            return "EN_ATTENTE_ENVOYE"
        return "EN_ATTENTE_RECU"


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("follower", "following")]
        constraints = [
            models.CheckConstraint(
<<<<<<< HEAD
                condition=~models.Q(follower=models.F("following")),
=======
                check=~models.Q(follower=models.F("following")),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                name="follow_cannot_follow_self",
            )
        ]
        indexes = [
            models.Index(fields=["follower", "created_at"]),
            models.Index(fields=["following", "created_at"]),
        ]

    def __str__(self):
        return f"{self.follower_id} follows {self.following_id}"


class Experience(models.Model):
    class ExperienceType(models.TextChoices):
        PROFESSIONAL = "professional", _("Professional")
        PROJECT = "project", _("Project")
        EVENT = "event", _("Event")
        VOLUNTEER = "volunteer", _("Volunteer")
        INTERNSHIP = "internship", _("Internship")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="experiences",
    )
    experience_type = models.CharField(
        max_length=20,
        choices=ExperienceType.choices,
        default=ExperienceType.PROFESSIONAL,
    )
    institution_name = models.CharField(max_length=255)
    role_title = models.CharField(max_length=255)
    project_url = models.URLField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-start_date"]),
        ]

    def clean(self):
        super().clean()

        self.institution_name = (self.institution_name or "").strip()
        self.role_title = (self.role_title or "").strip()
        self.project_url = (self.project_url or "").strip()

        if not self.institution_name:
<<<<<<< HEAD
            raise ValidationError(
                {"institution_name": _("Institution name is required.")}
            )
=======
            raise ValidationError({"institution_name": _("Institution name is required.")})
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        if not self.role_title:
            raise ValidationError({"role_title": _("Role title is required.")})

        if self.project_url and self.experience_type != self.ExperienceType.PROJECT:
            self.project_url = ""

        if not self.end_date:
            self.is_current = True
        elif self.is_current:
            self.end_date = None

        if self.end_date and self.start_date and self.start_date > self.end_date:
            raise ValidationError(
                {"end_date": _("End date must be greater than or equal to start date.")}
            )

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.is_current = True
        elif self.is_current:
            self.end_date = None
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.role_title} @ {self.institution_name}"
