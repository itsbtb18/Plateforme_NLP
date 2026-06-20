from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CIRBlock:
    block_id: str
    block_type: str
    text: str
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CIRChunk:
    chunk_id: str
    text: str
    token_count: int
    block_ids: list[str]
    section: str | None = None


@dataclass
class CanonicalIntermediateRepresentation:
    document_id: str
    source_language: str
    metadata: dict[str, Any]
    structural_blocks: list[CIRBlock]
    semantic_chunks: list[CIRChunk] = field(default_factory=list)
