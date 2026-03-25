from __future__ import annotations

from Plateforme.settings import *  # noqa: F401,F403

# Use SQLite so no external DB host is needed.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",  # type: ignore[name-defined]
    }
}

# Use in-memory cache so no Redis needed.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Keep channels in-process during tests.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Disable Celery task execution during tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable Elasticsearch during tests.
ELASTICSEARCH_DSL_AUTOSYNC = False
ELASTICSEARCH_DSL = {"default": {"hosts": "localhost:9200"}}

INSTALLED_APPS = [
    app
    for app in INSTALLED_APPS  # type: ignore[name-defined]
    if "elasticsearch" not in app.lower()
]

# Silence logging noise during tests.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {"class": "logging.NullHandler"},
    },
    "root": {"handlers": ["null"]},
}

# Use a fast password hasher.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Keep test runs self-contained and avoid broker/network dependencies.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Marker consumed by scraping models to disable vector-only fields.
SCRAPING_DISABLE_VECTOR_FIELD = True
