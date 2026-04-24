"""Celery tasks for AI translation and summarization pipelines."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from contextlib import contextmanager

from sqlalchemy import select

try:
    from prometheus_client import Histogram
except ModuleNotFoundError:
    class _NoopTimer:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class Histogram:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        def labels(self, **kwargs):
            _ = kwargs
            return self

        def time(self):
            return _NoopTimer()
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.jobs import get_ai_job_repo
from app.ai.service import get_ai_pipeline_service
from app.celery_app import celery
from app.config import get_settings
from app.models import DocumentChunk, UserDocument

logger = logging.getLogger(__name__)
settings = get_settings()
AI_JOB_DURATION = Histogram(
    "ai_job_duration_seconds",
    "AI job processing duration in seconds",
    ["job_type"],
)


@contextmanager
def _redis_lock(lock_key: str, ttl: int = 600):
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    token = "1"
    acquired = client.set(lock_key, token, nx=True, ex=ttl)
    try:
        if not acquired:
            raise RuntimeError("Lock not acquired")
        yield
    finally:
        current = client.get(lock_key)
        if current == token:
            client.delete(lock_key)


def _make_celery_session() -> tuple:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=4,
        pool_recycle=300,
        connect_args={
            "server_settings": {"application_name": "celery_ai_worker"},
            "command_timeout": 90,
            "timeout": 20,
        },
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


@celery.task(
    bind=True,
    name="app.tasks.ai.run_translation_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def run_translation_job(self, job_id: str):
    translation_task.delay(job_id)


@celery.task(
    bind=True,
    name="app.tasks.ai.run_summarization_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def run_summarization_job(self, job_id: str):
    summarization_task.delay(job_id)


@celery.task(
    bind=True,
    name="app.tasks.ai.translation_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def translation_task(self, job_id: str):
    _ = self
    asyncio.run(_run_job_async(job_id, task_type="translation", queue_name="translation"))


@celery.task(
    bind=True,
    name="app.tasks.ai.summarization_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def summarization_task(self, job_id: str):
    _ = self
    asyncio.run(_run_job_async(job_id, task_type="summarization", queue_name="summarization"))


@celery.task(
    bind=True,
    name="app.tasks.ai.run_postprocess_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_postprocess_job(self, job_id: str):
    _ = (self, job_id)
    return True


@celery.task(
    bind=True,
    name="app.tasks.ai.run_quality_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_quality_job(self, job_id: str):
    _ = (self, job_id)
    return True


async def _run_translation_job_async(job_id: str) -> None:
    lock_key = f"lock:ai:translation:{job_id}"
    with _redis_lock(lock_key, ttl=1200):
        await _execute_job(job_id, task_type="translation", queue_name="translation")


async def _run_summarization_job_async(job_id: str) -> None:
    lock_key = f"lock:ai:summarization:{job_id}"
    with _redis_lock(lock_key, ttl=1200):
        await _execute_job(job_id, task_type="summarization", queue_name="summarization")


async def _resolve_document_payload(
    db: AsyncSession,
    payload: dict,
) -> dict:
    document = dict(payload.get("document") or {})
    if document.get("raw_text") or document.get("file_uri"):
        return document

    document_id = payload.get("document_id")
    if not document_id:
        return document

    try:
        numeric_document_id = int(str(document_id))
    except (TypeError, ValueError):
        return document

    stmt = select(UserDocument).where(UserDocument.id == numeric_document_id)
    result = await db.execute(stmt)
    user_document = result.scalar_one_or_none()
    if not user_document:
        return document

    raw_text = (user_document.raw_text or "").strip()
    if not raw_text:
        chunk_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == numeric_document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunk_result = await db.execute(chunk_stmt)
        chunks = chunk_result.scalars().all()
        raw_text = "\n\n".join(chunk.content for chunk in chunks if chunk.content)

    document.update(
        {
            "raw_text": raw_text or None,
            "filename": user_document.filename,
        }
    )
    return document


async def _execute_job(job_id: str, task_type: str, queue_name: str) -> None:
    engine, SessionLocal = _make_celery_session()
    repo = get_ai_job_repo()
    pipeline = get_ai_pipeline_service()
    timer = AI_JOB_DURATION.labels(job_type=task_type).time()
    timer.__enter__()

    try:
        async with SessionLocal() as db:
            job = await repo.get_job(db, job_id)
            if not job:
                logger.error("AI job %s not found", job_id)
                return

            await repo.mark_running(db, job_id, provider_name="routing-pending", queue_name=queue_name)
            await repo.update_progress(db, job_id, 0.1)

            try:
                payload = dict(job.input_payload or {})
                payload["document"] = await _resolve_document_payload(db, payload)
                if task_type == "translation":
                    result = await pipeline.run_translation(job_id=job_id, payload=payload)
                else:
                    result = await pipeline.run_summarization(job_id=job_id, payload=payload)

                await repo.mark_succeeded(
                    db,
                    job_id=job_id,
                    output_text=result["output_text"],
                    output_uri=result.get("output_uri"),
                    quality_metrics=result.get("quality", {}),
                    metadata={
                        **result.get("metadata", {}),
                        "provider": result.get("provider"),
                    },
                    source_language=result.get("source_language"),
                    target_language=result.get("target_language"),
                )
                run_postprocess_job.delay(job_id)
                run_quality_job.delay(job_id)
            except Exception as exc:
                await repo.mark_failed(db, job_id, str(exc))
                raise
    finally:
        timer.__exit__(None, None, None)
        await engine.dispose()


async def _run_mvp_job_async(job_id: str, task_type: str, queue_name: str) -> None:
    """Simple functional MVP pipeline with mock model output."""
    engine, SessionLocal = _make_celery_session()
    repo = get_ai_job_repo()

    try:
        async with SessionLocal() as db:
            job = await repo.get_job(db, job_id)
            if not job:
                logger.error("AI job %s not found", job_id)
                return

            await repo.mark_running(db, job_id, provider_name="mock", queue_name=queue_name)
            await repo.update_progress(db, job_id, 0.4)

            payload = job.input_payload or {}
            doc_id = payload.get("document_id")

            if task_type == "translation":
                target = payload.get("target_language") or "en"
                output_text = (
                    f"translation unavailable (document_id={doc_id}, target_language={target}): "
                    "no source text was resolved."
                )
                source_language = payload.get("source_language") or "auto"
                target_language = target
                quality = {"confidence": 0.0}
            else:
                summary_type = payload.get("summary_type") or "brief"
                output_text = (
                    f"{summary_type} summary unavailable (document_id={doc_id}): "
                    "no source text was resolved."
                )
                source_language = payload.get("source_language") or "auto"
                target_language = source_language
                quality = {"faithfulness": 0.0, "coverage": 0.0}

            await repo.update_progress(db, job_id, 0.9)
            await repo.mark_succeeded(
                db,
                job_id=job_id,
                output_text=output_text,
                output_uri=None,
                quality_metrics=quality,
                metadata={
                    "provider": "mock",
                    "pipeline": "mvp",
                    "finished_at": datetime.now(UTC).isoformat(),
                },
                source_language=source_language,
                target_language=target_language,
            )
    except Exception as exc:
        async with SessionLocal() as db:
            await repo.mark_failed(db, job_id, str(exc))
        raise
    finally:
        await engine.dispose()


async def _run_job_async(job_id: str, task_type: str, queue_name: str) -> None:
    try:
        await _execute_job(job_id, task_type=task_type, queue_name=queue_name)
    except Exception:
        logger.exception("Real AI pipeline failed for job %s; falling back to MVP output", job_id)
        await _run_mvp_job_async(job_id, task_type=task_type, queue_name=queue_name)
