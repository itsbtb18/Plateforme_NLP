from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime

class ConversationRequest(BaseModel):
    """Request for conversation mode"""
    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    session_id: str = Field(..., description="Session identifier")
    history: List[Dict[str, str]] = Field(default=[], description="Conversation history")
    max_history: int = Field(default=20, ge=0, le=50)
    max_tokens: int = Field(default=24000, ge=100, le=50000)
    user_id: Optional[str] = None
    user_country: Optional[str] = None
    user_city: Optional[str] = None

class QuickQueryRequest(BaseModel):
    """Request for quick question mode (no context)"""
    question: str = Field(..., min_length=1, max_length=500, description="Quick question")

class PDFUploadRequest(BaseModel):
    """Request for PDF upload"""
    session_id: str
    filename: str

class PDFQuestionRequest(BaseModel):
    """Request for PDF-based question"""
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str

class RetrievedDoc(BaseModel):
    """Retrieved document from vector search"""
    id: int
    title: str
    content: str
    source: str  # platform_docs, nlp_knowledge, resources
    similarity: float

class ChatResponse(BaseModel):
    """Standard chat response"""
    answer: str
    source: str  # groq, platform_docs, nlp_knowledge, resources, hybrid
    session_id: str
    lang: Optional[str] = None
    retrieved_docs: Optional[List[RetrievedDoc]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SessionResponse(BaseModel):
    """Response for session creation"""
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class IngestionRequest(BaseModel):
    """Request for ingesting data"""
    type: str = Field(..., description="Type: platform_docs, nlp_knowledge, resources")
    data: List[Dict]

class IngestionResponse(BaseModel):
    """Response for data ingestion"""
    message: str
    count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
