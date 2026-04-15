from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import JobStatus, JobType
from app.models import AIJob


class AIJobRepository:
    async def create_job(
        self,
        db: AsyncSession,
        *,
        job_type: JobType,
        input_payload: dict[str, Any],
        owner_id: str,
        priority: int,
    ) -> AIJob:
        job = AIJob(
            job_id=str(uuid.uuid4()),
            job_type=job_type.value,
            status=JobStatus.QUEUED.value,
            owner_id=owner_id,
            priority=priority,
            input_payload=input_payload,
            progress=0.0,
            submitted_at=datetime.now(UTC),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def get_job(self, db: AsyncSession, job_id: str) -> AIJob | None:
        stmt = select(AIJob).where(AIJob.job_id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_running(self, db: AsyncSession, job_id: str, provider_name: str, queue_name: str) -> None:
        job = await self.get_job(db, job_id)
        if not job:
            return
        job.status = JobStatus.RUNNING.value
        job.provider_name = provider_name
        job.queue_name = queue_name
        job.started_at = datetime.now(UTC)
        await db.commit()

    async def update_progress(self, db: AsyncSession, job_id: str, progress: float) -> None:
        job = await self.get_job(db, job_id)
        if not job:
            return
        job.progress = max(0.0, min(1.0, progress))
        await db.commit()

    async def mark_failed(self, db: AsyncSession, job_id: str, error_message: str) -> None:
        job = await self.get_job(db, job_id)
        if not job:
            return
        job.status = JobStatus.FAILED.value
        job.error_message = error_message[:2000]
        job.completed_at = datetime.now(UTC)
        await db.commit()

    async def mark_succeeded(
        self,
        db: AsyncSession,
        *,
        job_id: str,
        output_text: str,
        output_uri: str | None,
        quality_metrics: dict[str, float],
        metadata: dict[str, Any],
        source_language: str | None,
        target_language: str | None,
    ) -> None:
        job = await self.get_job(db, job_id)
        if not job:
            return

        job.status = JobStatus.SUCCEEDED.value
        job.output_text = output_text
        job.output_uri = output_uri
        job.progress = 1.0
        job.quality_metrics = quality_metrics
        job.execution_metadata = metadata
        job.source_language = source_language
        job.target_language = target_language
        job.completed_at = datetime.now(UTC)
        await db.commit()


_repo: AIJobRepository | None = None


def get_ai_job_repo() -> AIJobRepository:
    global _repo
    if _repo is None:
        _repo = AIJobRepository()
    return _repo
