from datetime import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from accounts.managers import CustomUserManager
from institutions.models import Institution


from django.utils.crypto import get_random_string




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
  id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
  username = None
  email = models.EmailField(unique=True)
  full_name = models.CharField(max_length=255 , null=True , blank=True)
  institution = models.ForeignKey(Institution, on_delete=models.CASCADE , null=True , blank=True)
  bio = models.TextField(blank=True)
  status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Statut du compte"
    )
  avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name="Photo de profil"
    )
  objects = CustomUserManager() 
  is_email_verified = models.BooleanField(default=False)
  email_verification_code = models.CharField(max_length=6, blank=True, null=True)
  speciality = models.CharField(
        max_length=100,
        choices=SPECIALITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Spécialité"
    )
  linkedin_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="LinkedIn")
  twitter_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="Twitter")
  facebook_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="Facebook")
  is_verified = models.BooleanField(default=False, verbose_name="Profil vérifié")

  def generate_verification_code(self):
        self.email_verification_code = get_random_string(length=6, allowed_chars='0123456789')
        self.save()

  
  USERNAME_FIELD = 'email'  
  REQUIRED_FIELDS = [] 

 

  def __str__(self):
    return self.email







