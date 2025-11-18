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
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

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

    # Cloudinary - IMPORTANT: Order matters!
    'cloudinary_storage',
    'cloudinary',
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
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
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

# Database
DATABASE_URL = config('DATABASE_URL', default='', cast=str)
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in .env file")

DATABASES = {
    'default': dj_database_url.parse(str(DATABASE_URL), conn_max_age=600)
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

# ============================================
# CLOUDINARY CONFIGURATION - CRITICAL FIX
# ============================================
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configure Cloudinary FIRST
cloudinary.config(
    cloud_name=config('CLOUDINARY_CLOUD_NAME'),
    api_key=config('CLOUDINARY_API_KEY'),
    api_secret=config('CLOUDINARY_API_SECRET'),
    secure=True
)

# CRITICAL: Set BEFORE importing storage classes
os.environ['CLOUDINARY_CLOUD_NAME'] = str(config('CLOUDINARY_CLOUD_NAME'))
os.environ['CLOUDINARY_API_KEY'] = str(config('CLOUDINARY_API_KEY'))
os.environ['CLOUDINARY_API_SECRET'] = str(config('CLOUDINARY_API_SECRET'))

# Media files - Use Cloudinary for ALL uploads
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Cloudinary Storage Settings
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET')
}

# Static files
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = str(BASE_DIR / "staticfiles")

# Media settings - these are used as fallback but Cloudinary takes precedence
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================
# END CLOUDINARY CONFIGURATION
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
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "webmaster@localhost"

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
