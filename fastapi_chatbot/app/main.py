"""
FastAPI chatbot service — Arabic NLP Research Platform.

Thin controller layer. All business logic lives in services/.
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db, init_db
from app.config import get_settings
from app.schemas import (
    ConversationRequest,
    QuickQueryRequest,
    PDFQuestionRequest,
    UserDocQuestionRequest,
    LegalSearchRequest,
    PlatformSearchRequest,
    EntityExplainRequest,
    SessionRenameRequest,
    ChatResponse,
    SessionResponse,
    SessionListResponse,
    ChatHistoryResponse,
    DocumentUploadResponse,
    DocumentStatusResponse,
    DocumentListResponse,
    PlatformSearchResponse,
    PlatformDocumentIngestResponse,
)
from app.services.chat_logic import get_chat_logic
from app.services.memory import get_session_service
from app.services.documents import get_document_service
from app.services.platform_queries import get_platform_query_service
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FastAPI chatbot service...")
    await init_db()
    from app.services.qdrant import get_qdrant_service

    get_qdrant_service().ensure_collections()
    logger.info("Qdrant collections ready")

    # Preload the embedding model so it's ready before the first request
    from app.services.documents.embeddings import get_embedding_service

    get_embedding_service()
    logger.info("Embedding model preloaded")

    # Preload the Groq client
    from app.services.llm.client import get_groq_client

    get_groq_client()
    logger.info("Groq client preloaded")

    logger.info("FastAPI chatbot service ready")
    yield
    logger.info("Shutting down FastAPI chatbot service...")
    from app.services.elasticsearch_service import get_elasticsearch_service

    await get_elasticsearch_service().close()


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app = FastAPI(
    title="Arabic NLP Platform - Chatbot API",
    description="RAG-based chatbot with knowledge retrieval, platform queries, "
    "user documents, conversation management, and multilingual support.",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================================
# Health & warmup
# ==================================================================


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "fastapi-chatbot", "version": "4.0.0"}


@app.get("/warmup")
async def warmup():
    try:
        from app.services.embeddings import get_embedding_service

        get_embedding_service().encode_single("warmup")
        return {"status": "ready"}
    except Exception as e:
        logger.error("Warmup failed: %s", e)
        return {"status": "error", "message": str(e)}


# ==================================================================
# A) Knowledge Retrieval  (RAG — chat_logic)
# ==================================================================


@app.post("/conversation", response_model=ChatResponse)
async def conversation(
    request: ConversationRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_chat_logic().handle_conversation(request, db)
    except Exception as e:
        logger.error("Conversation error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process conversation")


async def _stream_conversation(request: ConversationRequest, db: AsyncSession):
    """Generator that yields SSE-formatted chunks."""
    try:
        async for chunk in get_chat_logic().handle_conversation_stream(request, db):
            line = json.dumps(chunk, ensure_ascii=False) + "\n"
            yield f"data: {line}\n\n"
    except Exception as e:
        logger.error("Stream conversation error: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/conversation/stream")
async def conversation_stream(
    request: ConversationRequest, db: AsyncSession = Depends(get_db)
):
    return StreamingResponse(
        _stream_conversation(request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/query", response_model=ChatResponse)
async def quick_query(request: QuickQueryRequest):
    try:
        return await get_chat_logic().handle_quick_query(
            request.question, request.language
        )
    except Exception as e:
        logger.error("Quick query error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process query")


@app.post("/legal_search", response_model=ChatResponse)
async def legal_search(request: LegalSearchRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await get_chat_logic().handle_legal_question(
            question=request.question,
            db=db,
            jurisdiction=request.jurisdiction,
            category=request.category,
            language=request.language,
        )
    except Exception as e:
        logger.error("Legal search error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process legal search")


# ==================================================================
# B) Platform Queries  (PostgreSQL — platform_queries service)
# ==================================================================


@app.post("/platform/search", response_model=PlatformSearchResponse)
async def platform_search(
    request: PlatformSearchRequest, db: AsyncSession = Depends(get_db)
):
    try:
        pqs = get_platform_query_service()
        results = await pqs.search_by_type(
            db,
            keyword=request.query,
            resource_type=request.resource_type,
            language=request.language,
            limit=request.limit,
        )
        nav = await pqs.get_navigation_help(request.query)
        return PlatformSearchResponse(
            results=results, total=len(results), navigation=nav
        )
    except Exception as e:
        logger.error("Platform search error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to search platform")


@app.get("/platform/stats")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    try:
        return await get_platform_query_service().get_platform_stats(db)
    except Exception as e:
        logger.error("Platform stats error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get stats")


@app.get("/platform/articles")
async def article_lookup(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    try:
        results = await get_platform_query_service().get_article_details(
            db, keyword=keyword, limit=limit
        )
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.error("Article lookup error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to look up articles")


@app.post("/platform/entity_explain", response_model=ChatResponse)
async def entity_explain(
    request: EntityExplainRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_chat_logic().handle_entity_explain(request, db)
    except Exception as e:
        logger.error("Entity explain error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to explain entity")


@app.post("/platform/document_ingest", response_model=PlatformDocumentIngestResponse)
async def platform_document_ingest(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    platform_document_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a platform document (article/thesis/memoir PDF) into the
    existing document pipeline.  Tags chunks with source='platform' so
    they don't mix with user uploads."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename required")
        file_bytes = await file.read()
        result = await get_document_service().upload(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename,
            session_id=session_id,
            user_id=user_id,
            source="platform",
            platform_document_id=platform_document_id,
        )
        return PlatformDocumentIngestResponse(
            document_id=result.document_id,
            filename=result.filename,
            status=result.status,
            session_id=result.session_id,
            message=result.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Platform document ingest error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to ingest document")


# ==================================================================
# C) User Documents  (document_service + Celery)
# ==================================================================


@app.post("/upload_document", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename required")
        file_bytes = await file.read()
        return await get_document_service().upload(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename,
            session_id=session_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to upload document")


@app.get("/document_status/{document_id}", response_model=DocumentStatusResponse)
async def document_status(
    document_id: int,
    user_id: str = Query(..., description="Document owner"),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_document_service().get_status(document_id, db, user_id=user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.get("/documents/{session_id}", response_model=DocumentListResponse)
async def list_documents(
    session_id: str,
    user_id: str = Query(..., description="Document owner"),
    db: AsyncSession = Depends(get_db),
):
    return await get_document_service().list_documents(session_id, db, user_id=user_id)


@app.post("/ask_document", response_model=ChatResponse)
async def ask_document(
    request: UserDocQuestionRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_chat_logic().handle_user_doc_question(
            question=request.question,
            session_id=request.session_id,
            db=db,
            document_id=request.document_id,
            document_ids=request.document_ids,
            user_id=request.user_id,
        )
    except Exception as e:
        logger.error("Ask document error: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to process document question"
        )


# ==================================================================
# D) Conversation System  (session_service)
# ==================================================================


@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    user_id: Optional[str] = None,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        sid = await get_session_service().create(
            db=db,
            user_id=user_id,
            user_country=user_country,
            user_city=user_city,
        )
        return SessionResponse(session_id=sid)
    except Exception as e:
        logger.error("Create session error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: str = Query(...),
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    return await get_session_service().list_sessions(user_id, db, include_inactive)


@app.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_session_history(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    messages = await get_session_service().get_history(session_id, db, limit)
    return ChatHistoryResponse(
        session_id=session_id, messages=messages, total=len(messages)
    )


@app.patch("/sessions/{session_id}/title")
async def rename_session(
    session_id: str, request: SessionRenameRequest, db: AsyncSession = Depends(get_db)
):
    await get_session_service().rename(session_id, request.title, db)
    return {"session_id": session_id, "title": request.title}


@app.post("/sessions/{session_id}/end")
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    await get_session_service().end(session_id, db)
    return {"message": "Session ended", "session_id": session_id}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    await get_session_service().delete(session_id, db)
    return {"message": "Session deleted", "session_id": session_id}


# ==================================================================
# Legacy endpoints (backward-compatible)
# ==================================================================


@app.post("/start_conversation", response_model=SessionResponse, deprecated=True)
async def start_conversation_legacy(
    user_id: Optional[str] = None,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await create_session(user_id, user_country, user_city, db)


@app.post("/end_conversation/{session_id}", deprecated=True)
async def end_conversation_legacy(session_id: str, db: AsyncSession = Depends(get_db)):
    return await end_session(session_id, db)


@app.post("/upload_pdf", deprecated=True)
async def upload_pdf_legacy(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    return await upload_document(file=file, session_id=session_id, db=db)


@app.post("/ask", response_model=ChatResponse, deprecated=True)
async def ask_pdf_question_legacy(
    request: PDFQuestionRequest, db: AsyncSession = Depends(get_db)
):
    return await get_chat_logic().handle_pdf_question(
        question=request.question,
        session_id=request.session_id,
        db=db,
    )


# ==================================================================
# Root
# ==================================================================


@app.get("/")
async def root():
    return {
        "service": "Arabic NLP Platform - Chatbot API",
        "version": "4.0.0",
        "endpoints": {
            "health": "GET /health",
            "warmup": "GET /warmup",
            "conversation": "POST /conversation",
            "quick_query": "POST /query",
            "legal_search": "POST /legal_search",
            "platform_search": "POST /platform/search",
            "platform_stats": "GET /platform/stats",
            "article_lookup": "GET /platform/articles?keyword=...",
            "entity_explain": "POST /platform/entity_explain",
            "document_ingest": "POST /platform/document_ingest",
            "upload_document": "POST /upload_document",
            "document_status": "GET /document_status/{id}",
            "list_documents": "GET /documents/{session_id}",
            "ask_document": "POST /ask_document",
            "create_session": "POST /sessions",
            "list_sessions": "GET /sessions?user_id=...",
            "session_history": "GET /sessions/{id}/history",
            "rename_session": "PATCH /sessions/{id}/title",
            "end_session": "POST /sessions/{id}/end",
            "delete_session": "DELETE /sessions/{id}",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
