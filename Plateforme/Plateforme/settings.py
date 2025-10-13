"""
Django settings for Plateforme project.
"""

from pathlib import Path
import os
from decouple import config
import dj_database_url

# --- Charger les variables d'environnement (.env) ---
# Assure-toi d'avoir "python-dotenv" dans requirements.txt (c'est le cas)
from dotenv import load_dotenv
load_dotenv()

# ----------------------------------------------------
# Chemins de base
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ----------------------------------------------------
# Sécurité & Debug
# ----------------------------------------------------
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-default-key')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Optionnel si tu utilises un nom de domaine ou 127.0.0.1 en HTTPS derrière un proxy
# CSRF_TRUSTED_ORIGINS = [ "https://ton-domaine.tld" ]

# ----------------------------------------------------
# Applications
# ----------------------------------------------------
INSTALLED_APPS = [
    # ASGI / Channels
    "daphne",
    "channels",

    # Apps projet
    "resources",
    "institutions",
    "accounts",
    "pages",
    "projects",
    "forum",
    "events",
    "QA",
    "notifications",
    "search",
    "chatbot",
    "translate",

    # Django/Allauth
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",

    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    # UI
    
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",

    # Elasticsearch
    #"django_elasticsearch_dsl",
]
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
SITE_ID = 1

# ----------------------------------------------------
# Middleware
# ----------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# ----------------------------------------------------
# URLs / Templates
# ----------------------------------------------------
ROOT_URLCONF = "Plateforme.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # requis par Allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notification_processor",
            ],
        },
    },
]

# ----------------------------------------------------
# ASGI / Channels
# ----------------------------------------------------
ASGI_APPLICATION = "Plateforme.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ----------------------------------------------------
# Base de données (PostgreSQL via .env)
# ----------------------------------------------------
DATABASE_URL = config('DATABASE_URL')
DATABASES = {
    'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
}

# ----------------------------------------------------
# Auth & Allauth
# ----------------------------------------------------
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_FORMS = {
    "signup": "accounts.forms.CustomUserCreationForm",
}

LOGIN_REDIRECT_URL = "pages:home"
ACCOUNT_LOGOUT_REDIRECT = "pages:home"

# ----------------------------------------------------
# i18n / l10n / tz (une seule section, pas de doublons)
# ----------------------------------------------------
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = "en"   # ou "ar" si tu veux l'arabe par défaut
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
# USE_L10N a été supprimé dans Django 5 -> ne pas l'utiliser

LANGUAGES = [
    ("en", _("English")),
    ("ar", _("Arabic")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# ----------------------------------------------------
# Fichiers statiques & médias
# ----------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = str(BASE_DIR / "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------
# Email (via .env) - SMTP Gmail (app password recommandé)
# ----------------------------------------------------
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Si aucune config n'est fournie, basculer sur la console pour dev
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "webmaster@localhost"

# ----------------------------------------------------
# Elasticsearch (via .env)
# ----------------------------------------------------
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": os.getenv("ELASTIC_URL", "http://localhost:9200"),
        "timeout": 120,
        "sniff_on_start": True,
    },
}
ELASTICSEARCH_DSL_AUTOSYNC = True
ELASTICSEARCH_DSL_AUTO_REFRESH = True

# ----------------------------------------------------
# Logging
# ----------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "chatbot": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

