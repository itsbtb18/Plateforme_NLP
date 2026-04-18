from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobType(str, Enum):
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DocumentInput(BaseModel):
    file_uri: str | None = Field(default=None, description="S3/MinIO URI or HTTPS URL")
    mime_type: str | None = Field(default=None)
    filename: str | None = Field(default=None)
    raw_text: str | None = Field(default=None, description="Direct text payload for low-latency requests")


class TranslationJobCreateRequest(BaseModel):
    document_id: str = Field(..., min_length=1)
    document: DocumentInput | None = None
    source_language: str | None = None
    target_language: str = Field(default="en", min_length=2, max_length=8)
    domain: str | None = Field(default=None, description="legal, scientific, healthcare, education, generic")
    glossary: dict[str, str] = Field(default_factory=dict)
    preserve_named_entities: bool = True
    priority: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SummarizationJobCreateRequest(BaseModel):
    document_id: str = Field(..., min_length=1)
    document: DocumentInput | None = None
    source_language: str | None = None
    summary_type: str = Field(default="brief", description="brief, detailed")
    style: str = Field(default="executive", description="brief, executive, detailed")
    max_words: int | None = Field(default=None, ge=50, le=5000)
    use_retrieval: bool = True
    domain: str | None = Field(default=None)
    priority: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus
    job_type: JobType
    submitted_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    job_type: JobType
    progress: float = 0.0
    provider: str | None = None
    queue: str | None = None
    error_message: str | None = None
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    quality: dict[str, float] = Field(default_factory=dict)


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    job_type: JobType
    output_text: str | None = None
    output_uri: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    quality: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime | None = None
