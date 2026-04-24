from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

try:
    from prometheus_client import Counter
except ModuleNotFoundError:
    class _NoopCounter:
        def labels(self, **kwargs):
            _ = kwargs
            return self

        def inc(self, amount: int = 1):
            _ = amount
            return None

    def Counter(*args, **kwargs):  # type: ignore[misc]
        _ = (args, kwargs)
        return _NoopCounter()

from app.ai.jobs import get_ai_job_repo
from app.ai.schemas import (
    JobAcceptedResponse,
    JobResultResponse,
    JobStatus,
    JobStatusResponse,
    JobType,
    SummarizationJobCreateRequest,
    TranslationJobCreateRequest,
)
from app.ai.security import enforce_rate_limit
from app.ai.storage import get_object_storage
from app.db import get_db
from app.tasks.ai_tasks import summarization_task, translation_task

router = APIRouter(tags=["ai-jobs"])
logger = logging.getLogger(__name__)

AI_JOB_SUBMITTED = Counter(
    "ai_job_submitted_total",
    "Total submitted AI jobs",
    ["job_type"],
)

@router.post("/translation/jobs", response_model=JobAcceptedResponse)
async def create_translation_job(
    payload: TranslationJobCreateRequest,
    claims: dict = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    logger.info("AI translation job request received: %s", payload.model_dump(mode="json"))
    if not payload.document_id or not str(payload.document_id).strip():
        raise HTTPException(status_code=400, detail="document_id is required")

    if payload.document is not None:
        storage = get_object_storage()
        storage.validate_file(
            mime_type=payload.document.mime_type,
            filename=payload.document.filename,
            size_bytes=None,
        )

    repo = get_ai_job_repo()
    job = await repo.create_job(
        db,
        job_type=JobType.TRANSLATION,
        input_payload=payload.model_dump(mode="json"),
        owner_id=str(claims.get("sub", "anonymous")),
        priority=payload.priority,
    )

    translation_task.delay(job.job_id)
    AI_JOB_SUBMITTED.labels(job_type=JobType.TRANSLATION.value).inc()
    return JobAcceptedResponse(
        job_id=job.job_id,
        status=JobStatus.QUEUED,
        job_type=JobType.TRANSLATION,
        submitted_at=job.submitted_at,
    )


@router.post("/summarization/jobs", response_model=JobAcceptedResponse)
async def create_summarization_job(
    payload: SummarizationJobCreateRequest,
    claims: dict = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    logger.info("AI summarization job request received: %s", payload.model_dump(mode="json"))
    if not payload.document_id or not str(payload.document_id).strip():
        raise HTTPException(status_code=400, detail="document_id is required")

    if payload.document is not None:
        storage = get_object_storage()
        storage.validate_file(
            mime_type=payload.document.mime_type,
            filename=payload.document.filename,
            size_bytes=None,
        )

    repo = get_ai_job_repo()
    job = await repo.create_job(
        db,
        job_type=JobType.SUMMARIZATION,
        input_payload=payload.model_dump(mode="json"),
        owner_id=str(claims.get("sub", "anonymous")),
        priority=payload.priority,
    )

    summarization_task.delay(job.job_id)
    AI_JOB_SUBMITTED.labels(job_type=JobType.SUMMARIZATION.value).inc()
    return JobAcceptedResponse(
        job_id=job.job_id,
        status=JobStatus.QUEUED,
        job_type=JobType.SUMMARIZATION,
        submitted_at=job.submitted_at,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    _: dict = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    repo = get_ai_job_repo()
    job = await repo.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        job_type=JobType(job.job_type),
        progress=job.progress,
        provider=job.provider_name,
        queue=job.queue_name,
        error_message=job.error_message,
        submitted_at=job.submitted_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        quality=job.quality_metrics or {},
    )


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(
    job_id: str,
    _: dict = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    repo = get_ai_job_repo()
    job = await repo.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED.value:
        raise HTTPException(status_code=409, detail=f"Job not completed: {job.status}")

    return JobResultResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        job_type=JobType(job.job_type),
        output_text=job.output_text,
        output_uri=(
            get_object_storage().create_signed_get_url(job.output_uri)
            if job.output_uri
            else None
        ),
        source_language=job.source_language,
        target_language=job.target_language,
        quality=job.quality_metrics or {},
        metadata=job.execution_metadata or {},
        completed_at=job.completed_at,
    )
