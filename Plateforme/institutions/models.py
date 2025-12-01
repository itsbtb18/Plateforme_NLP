import uuid
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage  # ADD THIS


class Country(models.Model):
    name_en = models.CharField(_("Country Name (English)"), max_length=100)
    name_ar = models.CharField(_("Country Name (Arabic)"), max_length=100)
    code = models.CharField(_("Country Code"), max_length=2, unique=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ['name_en']

    def __str__(self):
        from django.utils.translation import get_language
        current_lang = get_language()
        return self.name_ar if current_lang == 'ar' else self.name_en


class Specialty(models.Model):
    name_en = models.CharField(_("Specialty Name (English)"), max_length=100, unique=True, default='')
    name_ar = models.CharField(_("Specialty Name (Arabic)"), max_length=100, blank=True, default='')
    code = models.CharField(_("Specialty Code"), max_length=20, unique=True)

    class Meta:
        verbose_name = _("Specialty")
        verbose_name_plural = _("Specialties")
        ordering = ['name_en']

    def __str__(self):
        from django.utils.translation import get_language
        current_lang = get_language()
        return self.name_ar if current_lang == 'ar' else self.name_en

    
class Institution(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    TYPE = [
        ('School', _('School')),
        ('University', _('University')),
        ('Research Center', _('Research Center')),
        ('Other', _('Other')),
    ]
    name = models.CharField(_("Institution Name"), max_length=255)
    name_ar = models.CharField(_("Institution Name (Arabic)"), max_length=255, blank=True, default='')
    name_en = models.CharField(_("Institution Name (English)"), max_length=255, blank=True, default='')
    acronym = models.CharField(_("Acronym"), max_length=20, blank=True)
    type = models.CharField(max_length=255, choices=TYPE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name=_("Country"))
    city = models.CharField(_("City"), max_length=100)
    specialties = models.ManyToManyField(Specialty, verbose_name=_("Specialties"))
    
    # FIXED: Add Cloudinary storage
    logo = models.ImageField(
        _("Logo"),
        upload_to='institutions/logos/',
        storage=MediaCloudinaryStorage(),
        blank=True,
        null=True
    )
    
    website = models.URLField(_("Website"), blank=True)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Phone"), max_length=50, blank=True)
    address = models.TextField(_("Address"), blank=True)
    description = models.TextField(_("Description"), blank=True)
    
    # FIXED: Add Cloudinary storage
    image = models.ImageField(
        default='default.jpg',
        upload_to='institution_pics',
        storage=MediaCloudinaryStorage()
    )
    
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    # Use AUTH_USER_MODEL here:
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name=_("Created By"),
        related_name='created_institutions',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _("Institution")
        verbose_name_plural = _("Institutions")
        ordering = ['name']

    def __str__(self):
        from django.utils.translation import get_language
        current_lang = get_language()
        if current_lang == 'ar' and self.name_ar:
            return self.name_ar
        elif self.name_en:
            return self.name_en
        return self.name

    def get_absolute_url(self):
        return reverse('institutions:institution_detail', kwargs={'pk': self.pk})