from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db, init_db
from app.config import get_settings
from app.schemas import (
    ConversationRequest, QuickQueryRequest, PDFQuestionRequest,
    ChatResponse, SessionResponse, ErrorResponse
)
from app.services.chat_logic import get_chat_logic
from app.models import ChatSession
from sqlalchemy import select
import logging
from contextlib import asynccontextmanager
from typing import Optional
import PyPDF2
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown"""
    # Startup
    logger.info("🚀 Starting FastAPI chatbot service...")
    await init_db()
    logger.info("✅ FastAPI chatbot service ready")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down FastAPI chatbot service...")

# Create FastAPI app
app = FastAPI(
    title="Arabic NLP Platform - Chatbot API",
    description="RAG-based chatbot for Arabic NLP research platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "fastapi-chatbot",
        "version": "1.0.0"
    }

# Warmup endpoint to preload models
@app.get("/warmup")
async def warmup():
    """Warmup endpoint to preload embedding model"""
    try:
        from app.services.embeddings import get_embedding_service
        embedding_service = get_embedding_service()
        # Test encode to load model
        _ = embedding_service.encode_single("test")
        logger.info("✅ Models warmed up successfully")
        return {"status": "ready", "message": "Models preloaded"}
    except Exception as e:
        logger.error(f"❌ Warmup failed: {str(e)}")
        return {"status": "error", "message": str(e)}

# Start conversation
@app.post("/start_conversation", response_model=SessionResponse)
async def start_conversation(
    user_id: Optional[str] = None,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session"""
    try:
        chat_logic = get_chat_logic()
        session_id = await chat_logic.create_session(
            user_id=user_id,
            user_country=user_country,
            user_city=user_city,
            db=db
        )
        
        return SessionResponse(session_id=session_id)
    
    except Exception as e:
        logger.error(f"❌ Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")

# Conversation endpoint
@app.post("/conversation", response_model=ChatResponse)
async def conversation(
    request: ConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Handle conversation with RAG"""
    try:
        chat_logic = get_chat_logic()
        response = await chat_logic.handle_conversation(request, db)
        return response
    
    except Exception as e:
        logger.error(f"❌ Error in conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process conversation")

# Quick query endpoint
@app.post("/query", response_model=ChatResponse)
async def quick_query(request: QuickQueryRequest):
    """Handle quick question without context"""
    try:
        chat_logic = get_chat_logic()
        response = await chat_logic.handle_quick_query(request.question)
        return response
    
    except Exception as e:
        logger.error(f"❌ Error in quick query: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process query")

# Upload PDF
@app.post("/upload_pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Header(..., alias="session-id"),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process PDF file"""
    try:
        # Validate PDF
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Read PDF content
        pdf_bytes = await file.read()
        pdf_file = io.BytesIO(pdf_bytes)
        
        # Extract text from PDF
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)
        
        text_content = []
        for page in pdf_reader.pages:
            text_content.append(page.extract_text())
        
        full_text = "\n\n".join(text_content)
        
        # Store PDF context in session
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update session with PDF context using setattr
        setattr(session, 'pdf_context', full_text[:50000])  # Limit to 50k chars
        setattr(session, 'pdf_filename', file.filename)
        await db.commit()
        
        logger.info(f"✅ PDF uploaded: {file.filename} ({num_pages} pages)")
        
        return {
            "message": f"PDF uploaded successfully",
            "filename": file.filename,
            "pages": num_pages,
            "session_id": session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload PDF")

# Ask question about PDF
@app.post("/ask", response_model=ChatResponse)
async def ask_pdf_question(
    request: PDFQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Ask question about uploaded PDF"""
    try:
        chat_logic = get_chat_logic()
        response = await chat_logic.handle_pdf_question(
            question=request.question,
            session_id=request.session_id,
            db=db
        )
        return response
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error in PDF question: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process PDF question")

# End conversation
@app.post("/end_conversation/{session_id}")
async def end_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """End chat session"""
    try:
        chat_logic = get_chat_logic()
        await chat_logic.end_session(session_id, db)
        return {"message": "Session ended successfully", "session_id": session_id}
    
    except Exception as e:
        logger.error(f"❌ Error ending session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to end session")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Arabic NLP Platform - Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "start": "/start_conversation",
            "conversation": "/conversation",
            "query": "/query",
            "upload": "/upload_pdf",
            "ask": "/ask",
            "end": "/end_conversation/{session_id}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
