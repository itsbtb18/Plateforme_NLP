from __future__ import annotations

from app.ai.cir import CIRChunk, CanonicalIntermediateRepresentation
from app.config import get_settings

settings = get_settings()


class StructureAwareChunker:
    """Chunk while preserving structure (sections/paragraphs) with token fallback."""

    def __init__(self, max_tokens: int = 512, overlap_tokens: int = 64) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Lightweight estimate suitable for routing and chunk limits.
        return max(1, int(len(text.split()) * 1.3))

    def build_semantic_chunks(self, cir: CanonicalIntermediateRepresentation) -> list[CIRChunk]:
        chunks: list[CIRChunk] = []
        cursor = 0

        for block in cir.structural_blocks:
            if not block.text.strip():
                continue
            token_count = self._estimate_tokens(block.text)
            if token_count <= self.max_tokens:
                chunks.append(
                    CIRChunk(
                        chunk_id=f"chunk-{cursor}",
                        text=block.text,
                        token_count=token_count,
                        block_ids=[block.block_id],
                        section=block.section,
                    )
                )
                cursor += 1
                continue

            # Fallback: sentence-aware word windows.
            words = block.text.split()
            window = max(64, int(self.max_tokens / 1.3))
            overlap = max(16, int(self.overlap_tokens / 1.3))
            start = 0
            while start < len(words):
                end = min(len(words), start + window)
                fragment = " ".join(words[start:end])
                chunks.append(
                    CIRChunk(
                        chunk_id=f"chunk-{cursor}",
                        text=fragment,
                        token_count=self._estimate_tokens(fragment),
                        block_ids=[block.block_id],
                        section=block.section,
                    )
                )
                cursor += 1
                if end >= len(words):
                    break
                start = max(0, end - overlap)

        cir.semantic_chunks = chunks
        return chunks
