from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 0,
        "TEST": {
            "NAME": BASE_DIR / "test_db.sqlite3",
        },
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plateforme-nlp-test-cache",
    }
}

# Speed up tests and avoid external dependency side effects.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


# The project contains inconsistent migration dependencies in non-scraping apps.
# Disable migrations in test settings to build schema directly.
MIGRATION_MODULES = DisableMigrations()
