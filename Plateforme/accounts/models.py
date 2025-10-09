from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager
from institutions.models import Institution

class CustomUser(AbstractUser):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('active', 'Actif'),
        ('blocked', 'Bloqué'),
    ]
    SPECIALITY_CHOICES = [
        ('machine_learning', 'Machine Learning'),
        ('deep_learning', 'Deep Learning'),
        ('nlp', 'Traitement du Langage Naturel (NLP)'),
        ('computer_vision', 'Vision par Ordinateur'),
        ('reinforcement_learning', 'Apprentissage par Renforcement'),
        ('ai_ethics', 'Éthique de l\'IA'),
        ('robotics', 'Robotique et IA'),
        ('neural_networks', 'Réseaux de Neurones'),
        ('ai_security', 'Sécurité de l\'IA'),
        ('ai_healthcare', 'IA en Santé'),
        ('ai_finance', 'IA en Finance'),
        ('ai_education', 'IA en Éducation'),
        ('ai_transport', 'IA dans les Transports'),
        ('ai_agriculture', 'IA en Agriculture'),
        ('ai_energy', 'IA dans l\'Énergie'),
        ('ai_manufacturing', 'IA dans la Production'),
        ('ai_research', 'Recherche Fondamentale en IA'),
        ('autre', 'Autre Domaine de l\'IA'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, null=True, blank=True)
    bio = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    avatar = models.ImageField(upload_to='avatars/%Y/%m/%d/', null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_code = models.CharField(max_length=6, blank=True, null=True)
    speciality = models.CharField(max_length=100, choices=SPECIALITY_CHOICES, null=True, blank=True)
    linkedin_url = models.URLField(max_length=200, blank=True, null=True)
    twitter_url = models.URLField(max_length=200, blank=True, null=True)
    facebook_url = models.URLField(max_length=200, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def generate_verification_code(self):
        self.email_verification_code = get_random_string(length=6, allowed_chars='0123456789')
        self.save()

    def __str__(self):
        return self.email







