"""
Document service — document ownership & lifecycle.

PostgreSQL stores document metadata + ownership.
Text extraction happens here (sync, before Celery takes over).
Celery handles the heavy work (chunking + embedding).
Qdrant stores the resulting vectors.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import ChatSession, UserDocument
from app.schemas import (
    DocumentUploadResponse,
    DocumentStatusResponse,
    DocumentInfo,
    DocumentListResponse,
)
from app.config import get_settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentService:
    """Thin service for document upload, status, and listing.

    Heavy processing (chunking + embedding) is dispatched to Celery.
    """

    async def upload(
        self,
        db: AsyncSession,
        file_bytes: bytes,
        filename: str,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """Validate, extract text, persist metadata, dispatch Celery task."""
        fname = filename.lower()
        SUPPORTED = (".pdf", ".txt", ".docx", ".doc", ".xlsx")

        if not fname.endswith(SUPPORTED):
            raise ValueError(
                "Unsupported file type. Allowed: PDF, DOCX, DOC, TXT, XLSX."
            )

        file_size = len(file_bytes)
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit")

        # Extract text (lightweight — heavy chunking+embedding goes to Celery)
        from app.services.documents.processor import get_document_processor

        processor = get_document_processor()

        if fname.endswith(".pdf"):
            pages = processor.extract_pdf_text(file_bytes)
            raw_text = "\n\n".join(p["content"] for p in pages)
            file_type = "pdf"
        elif fname.endswith((".docx", ".doc")):
            pages = processor.extract_docx_text(file_bytes)
            raw_text = "\n\n".join(p["content"] for p in pages)
            file_type = "docx"
        elif fname.endswith(".xlsx"):
            pages = processor.extract_xlsx_text(file_bytes)
            raw_text = "\n\n".join(p["content"] for p in pages)
            file_type = "xlsx"
        else:
            raw_text = file_bytes.decode("utf-8", errors="replace")
            file_type = "txt"

        if not raw_text.strip():
            raise ValueError("No text content extracted from file")

        # Verify session exists
        sess = (
            await db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
        ).scalar_one_or_none()
        if not sess:
            raise LookupError("Session not found")

        effective_user = user_id or sess.user_id

        # --- Deduplication: if same filename already exists for this user,
        #     remove old document + its Qdrant chunks before re-uploading ---
        if effective_user:
            existing = (
                (
                    await db.execute(
                        select(UserDocument).where(
                            UserDocument.user_id == effective_user,
                            UserDocument.filename == filename,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if existing:
                from app.services.qdrant import (
                    get_qdrant_service,
                    COLLECTION_DOCUMENT_CHUNKS,
                )

                qdrant = get_qdrant_service()
                for old_doc in existing:
                    # Delete Qdrant vectors for old document
                    try:
                        qdrant.delete_by_filter(
                            COLLECTION_DOCUMENT_CHUNKS,
                            "document_id",
                            old_doc.id,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to delete Qdrant chunks for doc %d: %s",
                            old_doc.id,
                            e,
                        )
                    # Delete DB chunks
                    from app.models import DocumentChunk
                    from sqlalchemy import delete as sql_delete

                    await db.execute(
                        sql_delete(DocumentChunk).where(
                            DocumentChunk.document_id == old_doc.id
                        )
                    )
                    await db.delete(old_doc)
                await db.commit()
                logger.info(
                    "Replaced %d existing copy/copies of '%s'", len(existing), filename
                )

        # PostgreSQL: document metadata + ownership
        doc = UserDocument(
            user_id=effective_user,
            session_id=session_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            raw_text=raw_text[:200_000],
            status="pending",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Phase 8: Activate document session persistently so subsequent
        # conversation turns auto-route to document mode.
        sess.active_document_session = True
        sess.active_document_id = str(doc.id)
        sess.low_doc_similarity_streak = 0
        await db.commit()

        # Celery: heavy processing (chunking + embedding generation)
        from app.tasks import process_document

        try:
            process_document.delay(doc.id)
        except Exception as exc:
            logger.error("Failed to dispatch Celery task for doc %d: %s", doc.id, exc)
            # Document is already saved — mark it so the user knows
            doc.status = "queued"
            await db.commit()

        logger.info("Document uploaded: %s (id=%d)", filename, doc.id)
        return DocumentUploadResponse(
            document_id=doc.id,
            filename=filename,
            status="pending",
            session_id=session_id,
            message="Document uploaded and queued for processing",
        )

    async def get_status(
        self,
        document_id: int,
        db: AsyncSession,
        user_id: Optional[str] = None,
    ) -> DocumentStatusResponse:
        """Return document status.

        When *user_id* is provided the caller must be the owner
        (Phase 7 ownership enforcement).
        """
        doc = (
            await db.execute(select(UserDocument).where(UserDocument.id == document_id))
        ).scalar_one_or_none()
        if not doc:
            raise LookupError("Document not found")
        if user_id and doc.user_id and doc.user_id != user_id:
            raise PermissionError("Access denied — you do not own this document")
        return DocumentStatusResponse(
            document_id=doc.id,
            filename=doc.filename,
            status=doc.status,
            total_chunks=doc.total_chunks or 0,
            error_message=doc.error_message,
        )

    async def list_documents(
        self,
        session_id: str,
        db: AsyncSession,
        user_id: Optional[str] = None,
    ) -> DocumentListResponse:
        """List documents in a session.

        When *user_id* is provided only the owner's documents are returned.
        """
        conditions = [UserDocument.session_id == session_id]
        if user_id:
            conditions.append(UserDocument.user_id == user_id)
        stmt = (
            select(UserDocument)
            .where(*conditions)
            .order_by(UserDocument.created_at.desc())
        )
        docs = (await db.execute(stmt)).scalars().all()

        items = [
            DocumentInfo(
                document_id=d.id,
                filename=d.filename,
                file_type=d.file_type,
                status=d.status,
                total_chunks=d.total_chunks or 0,
                created_at=d.created_at,
            )
            for d in docs
        ]
        return DocumentListResponse(
            session_id=session_id,
            documents=items,
            total=len(items),
        )


# Singleton
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
