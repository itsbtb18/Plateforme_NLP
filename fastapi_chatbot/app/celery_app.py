"""
Celery application for background task processing.

Used for:
- Document chunking & embedding generation
- Batch ingestion of knowledge bases
- Chat history summarisation
"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "chatbot_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,  # 10 min soft limit
    task_time_limit=900,  # 15 min hard limit
    broker_connection_retry_on_startup=True,
    task_default_queue="chatbot",
    task_routes={
        "app.tasks.process_document": {"queue": "documents"},
        "app.tasks.summarise_chat_history": {"queue": "chatbot"},
        "app.tasks.ingest_legal_batch": {"queue": "ingestion"},
        "app.tasks.crawl_and_index_url": {"queue": "ingestion"},
        "app.tasks.summarise_text": {"queue": "chatbot"},
        "app.tasks.reindex_collection": {"queue": "documents"},
        "app.tasks.ai.run_translation_job": {"queue": "translation"},
        "app.tasks.ai.run_summarization_job": {"queue": "summarization"},
        "app.tasks.ai.translation_task": {"queue": "translation"},
        "app.tasks.ai.summarization_task": {"queue": "summarization"},
        "app.tasks.ai.run_postprocess_job": {"queue": "postprocess"},
        "app.tasks.ai.run_quality_job": {"queue": "quality"},
    },
)

celery.autodiscover_tasks(["app.tasks"])
