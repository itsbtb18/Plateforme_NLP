"""
Django settings for Plateforme project.
"""

from pathlib import Path
import os
from decouple import config
import dj_database_url

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Security & Debug
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-default-key')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,*', cast=lambda v: [s.strip() for s in v.split(',')])

# Applications
INSTALLED_APPS = [
    # ASGI / Channels
    "daphne",
    "channels",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    'django.contrib.staticfiles',

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

    # Allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    # UI
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
SITE_ID = 1

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.two_factor_auth.TwoFactorAuthenticationMiddleware",
]

# URLs / Templates
ROOT_URLCONF = "Plateforme.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notification_processor",
            ],
        },
    },
]

# ASGI / Channels
ASGI_APPLICATION = "Plateforme.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Redis Cache Configuration
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_KWARGS": {"decode_responses": True},
            "CONNECTION_POOL_KWARGS": {"max_connections": 50}
        }
    }
}

# Parse REDIS_URL for 2FA utilities
from urllib.parse import urlparse
parsed_redis = urlparse(redis_url)
REDIS_HOST = parsed_redis.hostname or '127.0.0.1'
REDIS_PORT = parsed_redis.port or 6379
REDIS_DB = int(parsed_redis.path.split('/')[-1] or 0)
REDIS_PASSWORD = parsed_redis.password or None

# Database
DATABASE_URL = config('DATABASE_URL', default='', cast=str)

# Only parse DATABASE_URL if it's provided (allows Docker build to succeed)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(str(DATABASE_URL), conn_max_age=600, conn_health_checks=True)
    }
else:
    # Fallback for Docker build (will be overridden by env vars at runtime)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'nlp_platform',
            'USER': 'nlp_admin',
            'PASSWORD': '1008',
            'HOST': 'db',
            'PORT': '5432',
        }
    }

# Auth & Allauth
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

# i18n / l10n / tz
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", _("English")),
    ("ar", _("Arabic")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# Format de date personnalisé par langue
USE_L10N = False  # Désactiver pour utiliser nos formats personnalisés

# Formats de date pour chaque langue
FORMAT_MODULE_PATH = [
    'Plateforme.formats',
]

# ============================================
# FILE STORAGE CONFIGURATION
# ============================================

# Static files configuration
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = str(BASE_DIR / "staticfiles")

# Media files configuration - Local storage
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / 'media'

# Django 5.1+ STORAGES configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ============================================
# END FILE STORAGE CONFIGURATION
# ============================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email Configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
else:
    # Use file backend for development/testing
    # Emails will be saved to /tmp/django-emails/
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = "/tmp/django-emails"
    DEFAULT_FROM_EMAIL = "noreply@plateforme-nlp.com"

# Elasticsearch
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": os.getenv("ELASTIC_URL", "http://localhost:9200"),
        "timeout": 120,
        "sniff_on_start": True,
    },
}
ELASTICSEARCH_DSL_AUTOSYNC = True
ELASTICSEARCH_DSL_AUTO_REFRESH = True

# Chatbot / FastAPI Configuration
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://nlp_fastapi:8000")
FASTAPI_API_KEY = os.getenv("FASTAPI_API_KEY", "")
CHATBOT_MAX_HISTORY = int(os.getenv("CHATBOT_MAX_HISTORY", "20"))
CHATBOT_MAX_TOKENS = int(os.getenv("CHATBOT_MAX_TOKENS", "24000"))
CHATBOT_TIMEOUT = int(os.getenv("CHATBOT_TIMEOUT", "180"))
CHATBOT_MAX_FILE_SIZE = int(os.getenv("CHATBOT_MAX_FILE_SIZE", "10485760"))  # 10MB

# Logging
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
