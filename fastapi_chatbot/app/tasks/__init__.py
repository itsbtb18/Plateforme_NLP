"""
app.tasks — Celery task package.

Import all task modules so Celery auto-discovers them.
"""
from app.tasks.document_tasks import process_document          # noqa: F401
from app.tasks.summary_tasks import (                          # noqa: F401
    summarise_chat_history,
    summarise_text,
)
from app.tasks.ingestion_tasks import (                        # noqa: F401
    ingest_legal_batch,
    crawl_and_index_url,
)
from app.tasks.maintenance_tasks import reindex_collection     # noqa: F401
from app.tasks.ai_tasks import (                               # noqa: F401
    run_translation_job,
    run_summarization_job,
    translation_task,
    summarization_task,
    run_postprocess_job,
    run_quality_job,
)
