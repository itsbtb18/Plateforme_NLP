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
SECRET_KEY = config("SECRET_KEY", default="django-insecure-your-default-key")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,*",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

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
    "django.contrib.staticfiles",
    # Elasticsearch
    "django_elasticsearch_dsl",
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
    "direct_messages",
    "sharing",
    "translate",
    "scraping",
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
    "pages.middleware.SecurityLogMiddleware",
    "pages.middleware.AdminPanelSecurityMiddleware",
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
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
        },
    }
}

# Parse REDIS_URL for 2FA utilities
from urllib.parse import urlparse

parsed_redis = urlparse(redis_url)
REDIS_HOST = parsed_redis.hostname or "127.0.0.1"
REDIS_PORT = parsed_redis.port or 6379
REDIS_DB = int(parsed_redis.path.split("/")[-1] or 0)
REDIS_PASSWORD = parsed_redis.password or None

# Database
DATABASE_URL = config("DATABASE_URL", default="", cast=str)

# Only parse DATABASE_URL if it's provided (allows Docker build to succeed)
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            str(DATABASE_URL), conn_max_age=600, conn_health_checks=True
        )
    }
else:
    # Fallback for Docker build (will be overridden by env vars at runtime)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "nlp_platform",
            "USER": "nlp_admin",
            "PASSWORD": "1008",
            "HOST": "db",
            "PORT": "5432",
        }
    }

# Auth & Allauth
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_FORMS = {
    "signup": "accounts.forms.CustomUserCreationForm",
}

# Remember Me Configuration
ACCOUNT_SESSION_REMEMBER = None  # Let the checkbox control remember me
ACCOUNT_REMEMBER_ME_EXPIRY = 604800  # 1 week in seconds (7 days)

LOGIN_REDIRECT_URL = "pages:home"
ACCOUNT_LOGOUT_REDIRECT = "pages:home"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {
            "user_attributes": ("email", "full_name", "full_name_en", "full_name_ar"),
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Session Security Settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds (14 days)
SESSION_COOKIE_SECURE = not DEBUG  # Use secure cookies in production
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SAMESITE = "Lax"  # Protect against CSRF
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Don't expire at browser close by default
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on each request

# CSRF Security
CSRF_COOKIE_SECURE = not DEBUG  # Use secure CSRF cookie in production
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Security Headers (for production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

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
    "Plateforme.formats",
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
MEDIA_ROOT = BASE_DIR / "media"

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB

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
EMAIL_HOST = os.getenv("EMAIL_HOST") or "smtp.gmail.com"
EMAIL_PORT = int(os.getenv("EMAIL_PORT") or "587")
EMAIL_USE_TLS = (os.getenv("EMAIL_USE_TLS") or "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER") or ""
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD") or ""

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
        "hosts": os.getenv(
            "ELASTICSEARCH_HOST", os.getenv("ELASTIC_URL", "http://localhost:9200")
        ),
        "timeout": 120,
        "sniff_on_start": False,  # Disable sniffing to prevent connection errors in Docker
    },
}
# Disable autosync to prevent creation failures when Elasticsearch is unavailable
# Resources can be manually indexed later using: python manage.py search_index --rebuild
ELASTICSEARCH_DSL_AUTOSYNC = os.getenv("ELASTICSEARCH_DSL_AUTOSYNC", "False").lower() == "true"
ELASTICSEARCH_DSL_AUTO_REFRESH = True

# Chatbot / FastAPI Configuration
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
FASTAPI_API_KEY = os.getenv("FASTAPI_API_KEY", "")
CHATBOT_MAX_HISTORY = int(os.getenv("CHATBOT_MAX_HISTORY", "20"))
CHATBOT_MAX_TOKENS = int(os.getenv("CHATBOT_MAX_TOKENS", "8192"))
CHATBOT_TIMEOUT = int(os.getenv("CHATBOT_TIMEOUT", "180"))
CHATBOT_MAX_FILE_SIZE = int(os.getenv("CHATBOT_MAX_FILE_SIZE", "20971520"))  # 20MB

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
        "resources": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "projects": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "forum": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
