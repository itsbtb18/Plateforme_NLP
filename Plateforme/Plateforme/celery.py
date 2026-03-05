"""
Celery application for the Django Plateforme project.

Used for background scraping tasks and scheduled jobs.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")

app = Celery("Plateforme")

# Load config from Django settings, using the CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()
