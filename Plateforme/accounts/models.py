from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator, EmailValidator
from django.core.exceptions import ValidationError
import uuid
import re
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .managers import CustomUserManager
from institutions.models import Institution


class CustomUser(AbstractUser):
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('active', _('Active')),
        ('blocked', _('Blocked')),
    ]
    
    SPECIALITY_CHOICES = [
        ('machine_learning', _('Machine Learning')),
        ('deep_learning', _('Deep Learning')),
        ('nlp', _('Natural Language Processing (NLP)')),
        ('computer_vision', _('Computer Vision')),
        ('reinforcement_learning', _('Reinforcement Learning')),
        ('ai_ethics', _('AI Ethics')),
        ('robotics', _('Robotics and AI')),
        ('neural_networks', _('Neural Networks')),
        ('ai_security', _('AI Security')),
        ('ai_healthcare', _('AI in Healthcare')),
        ('ai_finance', _('AI in Finance')),
        ('ai_education', _('AI in Education')),
        ('ai_transport', _('AI in Transportation')),
        ('ai_agriculture', _('AI in Agriculture')),
        ('ai_energy', _('AI in Energy')),
        ('ai_manufacturing', _('AI in Manufacturing')),
        ('ai_research', _('Fundamental AI Research')),
        ('autre', _('Other AI Field')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('full name')
    )
    full_name_ar = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Full Name (Arabic)'),
        help_text=_('Full name in Arabic')
    )
    full_name_en = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Full Name (English)'),
        help_text=_('Full name in English')
    )
    bio = models.TextField(
        blank=True,
        verbose_name=_('biography')
    )
    bio_ar = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Biography (Arabic)')
    )
    bio_en = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Biography (English)')
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('institution')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('status')
    )
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_('profile picture')
    )
    is_email_verified = models.BooleanField(
        default=False,
        verbose_name=_('email verified')
    )
    email_verification_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name=_('email verification code')
    )
    speciality = models.CharField(
        max_length=100,
        choices=SPECIALITY_CHOICES,
        null=True,
        blank=True,
        verbose_name=_('field of specialization in AI')
    )
    linkedin_url = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('LinkedIn URL')
    )
    twitter_url = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('Twitter URL')
    )
    facebook_url = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('Facebook URL')
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_('verified')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('active')
    )

    objects: CustomUserManager = CustomUserManager()  # type: ignore[assignment]

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name_en', 'full_name_ar']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def generate_verification_code(self):
        self.email_verification_code = get_random_string(
            length=6,
            allowed_chars='0123456789'
        )
        self.save()

    def get_localized_full_name(self):
        """Return full name based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.full_name_ar:
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
        
        if lang and lang.startswith('ar'):
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
        if lang and lang.startswith('ar'):
            return self.full_name_ar or ''
        return self.full_name_en or ''

    @property
    def bio_display(self):
        """Return bio based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar'):
            return self.bio_ar or ''
        return self.bio_en or ''

    def get_localized_bio(self):
        """Return bio based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.bio_ar:
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
        social_fields = ['linkedin_url', 'twitter_url', 'facebook_url']
        
        for field_name in social_fields:
            url = getattr(self, field_name, None)
            if url:
                try:
                    url_validator(url)
                except ValidationError:
                    raise ValidationError({field_name: _('Enter a valid URL.')})
        
        # Validate LinkedIn URL format
        if self.linkedin_url and 'linkedin.com' not in self.linkedin_url.lower():
            raise ValidationError({'linkedin_url': _('Please enter a valid LinkedIn URL.')})
        
        # Validate Twitter URL format
        if self.twitter_url:
            twitter_lower = self.twitter_url.lower()
            if 'twitter.com' not in twitter_lower and 'x.com' not in twitter_lower:
                raise ValidationError({'twitter_url': _('Please enter a valid Twitter/X URL.')})

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
        return self.email.split('@')[0]

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