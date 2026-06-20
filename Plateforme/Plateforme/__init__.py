# Load Celery app so that @shared_task decorators use it when available.
try:
	from .celery import app as celery_app
except Exception:  # pragma: no cover - optional runtime dependency
	celery_app = None

__all__ = ("celery_app",)
