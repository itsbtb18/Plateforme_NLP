"""
Celery Application Configuration
"""
import logging
from celery import Celery
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "cv_processing",
    broker=settings.get_celery_broker_url,
    backend=settings.get_celery_result_backend_url
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Auto-discover tasks from app.tasks
celery_app.autodiscover_tasks(['app.tasks'])

logger.info(f"Celery configured with broker: {settings.get_celery_broker_url}")
logger.info(f"Celery results backend: {settings.get_celery_result_backend_url}")


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connection"""
    logger.info(f"Request: {self.request!r}")
