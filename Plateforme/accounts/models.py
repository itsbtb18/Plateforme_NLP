from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
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
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('institution')
    )
    bio = models.TextField(
        blank=True,
        verbose_name=_('biography')
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

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def generate_verification_code(self):
        self.email_verification_code = get_random_string(
            length=6,
            allowed_chars='0123456789'
        )
        self.save()

    def __str__(self):
        return self.email