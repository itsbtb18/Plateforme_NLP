"""
Django settings for Plateforme project.
"""

import importlib.util
import os
from pathlib import Path

import dj_database_url
from decouple import config
from django.core.exceptions import ImproperlyConfigured

try:
    from celery.schedules import crontab

    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False

    def crontab(*args, **kwargs):
        return None

# Load environment variables for local, non-Docker runs.
from dotenv import load_dotenv

load_dotenv()

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str | None = None, aliases: tuple[str, ...] = ()):
    """Read an environment variable with optional aliases and empty-value guard."""
    for key in (name, *aliases):
        value = os.environ.get(key)
        if value is not None and value != "":
            return value
    return default


def _env_bool(name: str, default: bool = False, aliases: tuple[str, ...] = ()) -> bool:
    value = _env_str(name, aliases=aliases)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# Security & Debug
SECRET_KEY = _env_str("DJANGO_SECRET_KEY", aliases=("SECRET_KEY",))
DEBUG = _env_bool("DJANGO_DEBUG", default=False, aliases=("DEBUG",))
ALLOWED_HOSTS = _env_str(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    aliases=("ALLOWED_HOSTS",),
).split(",")
INTERNAL_IPS = [
    "127.0.0.1",
    "172.25.0.5",
    "172.25.0.0/16",
]
PROMETHEUS_ALLOWED_IPS = [
    "172.25.0.0/16",
]
PROMETHEUS_ALLOWED_NETWORKS = os.environ.get(
    "PROMETHEUS_ALLOWED_NETWORKS",
    "172.25.0.0/16,172.16.0.0/12,127.0.0.1/32",
).split(",")

if not DEBUG and SECRET_KEY == "django-insecure-your-default-key":
    raise ImproperlyConfigured(
        "Refusing to start with default SECRET_KEY while DEBUG is False."
    )

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Missing SECRET_KEY: set DJANGO_SECRET_KEY (or SECRET_KEY) in the environment."
    )

if not DEBUG and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "Refusing to start with wildcard ALLOWED_HOSTS while DEBUG is False."
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
    "taxonomy",
    "accounts",
    "pages",
    "projects",
    "project_chatroom",
    "forum",
    "events",
    "feed",
    "notifications",
    "search",
    "chatbot",
    "direct_messages",
    "sharing",
    "translate",
    "scraping",
    "settings",
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

if CELERY_AVAILABLE and importlib.util.find_spec("django_celery_beat") is not None:
    INSTALLED_APPS.append("django_celery_beat")

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
                "core.context_processors.runtime_urls",
                "notifications.context_processors.notification_processor",
            ],
        },
    },
]

# ASGI / Channels
ASGI_APPLICATION = "Plateforme.asgi.application"

CHANNEL_LAYER_BACKEND = os.getenv("CHANNEL_LAYER_BACKEND", "redis").strip().lower()

if CHANNEL_LAYER_BACKEND == "redis":
    CHANNEL_REDIS_URL = os.getenv("CHANNEL_REDIS_URL", "redis://127.0.0.1:6379/5")
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CHANNEL_REDIS_URL],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# Redis Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "nlp_cache",
    }
}

# Parse REDIS_URL for 2FA utilities
from urllib.parse import urlparse

redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/2")
parsed_redis = urlparse(redis_url)
REDIS_HOST = parsed_redis.hostname or "127.0.0.1"
REDIS_PORT = parsed_redis.port or 6379
REDIS_DB = (
    int(parsed_redis.path.split("/")[-1] or 0)
    if parsed_redis.path.split("/")[-1]
    else 0
)
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
CSRF_COOKIE_HTTPONLY = False
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

# 2FA OTP hashing pepper (required by accounts/two_factor_utils.py)
# Set OTP_PEPPER explicitly in environment for production.
OTP_PEPPER = os.getenv("OTP_PEPPER") or SECRET_KEY

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
ELASTICSEARCH_DSL_AUTOSYNC = (
    os.getenv("ELASTICSEARCH_DSL_AUTOSYNC", "False").lower() == "true"
)
ELASTICSEARCH_DSL_AUTO_REFRESH = True

# Chatbot / FastAPI Configuration
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
FASTAPI_BROWSER_URL = os.getenv("FASTAPI_BROWSER_URL", "/ai")
FASTAPI_LOCAL_BROWSER_URL = os.getenv("FASTAPI_LOCAL_BROWSER_URL", "http://localhost:8000")
FASTAPI_API_KEY = os.getenv("FASTAPI_API_KEY", "")
CHATBOT_MAX_HISTORY = int(os.getenv("CHATBOT_MAX_HISTORY", "20"))
CHATBOT_MAX_TOKENS = int(os.getenv("CHATBOT_MAX_TOKENS", "8192"))
CHATBOT_TIMEOUT = int(os.getenv("CHATBOT_TIMEOUT", "180"))
CHATBOT_MAX_FILE_SIZE = int(os.getenv("CHATBOT_MAX_FILE_SIZE", "20971520"))  # 20MB

# Translation / Summarization Service
TS_SERVICE_PORT = os.getenv("TS_SERVICE_PORT", "8010")
# Auto-detect if we are running in Docker to set the correct host name for internal networking.
IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_TS_HOST = "translation_summarization" if IS_DOCKER else "localhost"
TS_SERVICE_HOST = os.getenv("TS_SERVICE_HOST", DEFAULT_TS_HOST)
TS_SERVICE_URL = os.getenv(
    "TS_SERVICE_URL",
    f"http://{TS_SERVICE_HOST}:{TS_SERVICE_PORT}",
)
TS_SERVICE_API_KEY = os.getenv("TS_SERVICE_API_KEY", "")
TS_SERVICE_TIMEOUT = int(os.getenv("TS_SERVICE_TIMEOUT", "300"))

# Logging
LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "scraping_json": {
            "()": "scraping.scraping_logger.ScrapingJSONFormatter",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "scraping_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "scraping.log"),
            "maxBytes": 50 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "scraping_json",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
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
        "scraping": {
            "handlers": ["scraping_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ============================================
# GROQ LLM — Scraping Validation
# ============================================
GROQ_SCRAPING_API_KEY = os.getenv("GROQ_SCRAPING_API_KEY", "")
GROQ_SCRAPING_MODEL = os.getenv("GROQ_SCRAPING_MODEL", "llama-3.3-70b-versatile")
GROQ_SCRAPING_TIMEOUT = 30  # seconds per LLM call
GROQ_SCRAPING_MAX_RETRIES = 2  # JSON-parse retries
SCRAPING_LLM_PRIMARY_PROVIDER = os.getenv("SCRAPING_LLM_PRIMARY_PROVIDER", "gemini")
SCRAPING_LLM_FALLBACK_PROVIDER = os.getenv("SCRAPING_LLM_FALLBACK_PROVIDER", "groq")
SCRAPING_LLM_MODE = os.getenv("SCRAPING_LLM_MODE", "primary_with_fallback")
GEMINI_SCRAPING_API_KEY = os.getenv("GEMINI_SCRAPING_API_KEY", "")
GEMINI_SCRAPING_MODEL = os.getenv("GEMINI_SCRAPING_MODEL", "gemini-3.5-preview")
GEMINI_SCRAPING_TIMEOUT = int(os.getenv("GEMINI_SCRAPING_TIMEOUT", "30"))
GEMINI_SCRAPING_MAX_RETRIES = int(os.getenv("GEMINI_SCRAPING_MAX_RETRIES", "2"))
GEMINI_SCRAPING_MAX_RPM = int(os.getenv("GEMINI_SCRAPING_MAX_RPM", "10"))
PLAYWRIGHT_THRESHOLD = int(os.environ.get("PLAYWRIGHT_THRESHOLD", "200"))

# ============================================
# CELERY CONFIGURATION
# ============================================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://:redis123@redis:6379/3")
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND", "redis://:redis123@redis:6379/4"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SOFT_TIME_LIMIT = 600  # 10 min soft limit
CELERY_TASK_TIME_LIMIT = 900  # 15 min hard limit
CELERY_TASK_DEFAULT_QUEUE = "scraping"

CELERY_BEAT_SCHEDULE = (
    {
        "update-adaptive-schedules": {
            "task": "scraping.tasks.update_adaptive_schedules",
            "schedule": crontab(hour=3, minute=0),
        }
    }
    if CELERY_AVAILABLE
    else {}
)
