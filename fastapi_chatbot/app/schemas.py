from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ConversationRequest(BaseModel):
    """Request for conversation mode"""

    question: str = Field(
        ..., min_length=1, max_length=2000, description="User question"
    )
    session_id: str = Field(..., description="Session identifier")
    history: List[Dict[str, str]] = Field(
        default=[], description="Conversation history"
    )
    max_history: int = Field(default=20, ge=0, le=50)
    max_tokens: int = Field(default=2048, ge=100, le=8192)
    user_id: Optional[str] = None
    user_country: Optional[str] = None
    user_city: Optional[str] = None
    # Current user profile — so the LLM knows who is asking
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_bio: Optional[str] = None
    user_institution: Optional[str] = None
    user_speciality: Optional[str] = None


class QuickQueryRequest(BaseModel):
    """Request for quick question mode (no context)"""

    question: str = Field(
        ..., min_length=1, max_length=500, description="Quick question"
    )
    language: Optional[str] = Field(
        None, description="Force response language (ar/en/fr)"
    )


class PDFQuestionRequest(BaseModel):
    """Request for PDF-based question"""

    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str


class UserDocQuestionRequest(BaseModel):
    """Ask a question against user-uploaded documents"""

    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str
    user_id: str = Field(..., description="Owner — only their documents are searched")
    document_id: Optional[int] = None  # None = search all user docs in session
    document_ids: Optional[List[int]] = None  # Filter to specific document(s)


class LegalSearchRequest(BaseModel):
    """Search legal knowledge base"""

    question: str = Field(..., min_length=1, max_length=2000)
    jurisdiction: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None


class PlatformSearchRequest(BaseModel):
    """Search platform content (courses, documents, tools, events, etc.)"""

    query: str = Field(..., min_length=1, max_length=500)
    resource_type: Optional[str] = Field(
        None,
        description="Filter by type: course, document, article, thesis, tool, corpus, event, institution, project",
    )
    language: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class SessionRenameRequest(BaseModel):
    """Rename a chat session"""

    title: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RetrievedDoc(BaseModel):
    """Retrieved document from vector search"""

    id: int
    title: str
    content: str
    source: str
    similarity: float


class ChatResponse(BaseModel):
    """Standard chat response"""

    answer: str
    source: str
    session_id: str
    lang: Optional[str] = None
    retrieved_docs: Optional[List[RetrievedDoc]] = None
    platform_results: Optional[List[Dict[str, Any]]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionResponse(BaseModel):
    """Response for session creation"""

    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionInfo(BaseModel):
    """Session summary for sidebar listing"""

    session_id: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    is_active: bool = True
    message_count: int = 0
    preferred_language: Optional[str] = None


class SessionListResponse(BaseModel):
    """List of user sessions for sidebar"""

    sessions: List[SessionInfo]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document for async processing"""

    document_id: int
    filename: str
    status: str
    session_id: str
    message: str


class DocumentStatusResponse(BaseModel):
    """Response for document processing status"""

    document_id: int
    filename: str
    status: str
    total_chunks: int
    error_message: Optional[str] = None


class DocumentInfo(BaseModel):
    """User document info"""

    document_id: int
    filename: str
    file_type: Optional[str] = None
    status: str
    total_chunks: int
    created_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """List of user documents in a session"""

    session_id: str
    documents: List[DocumentInfo]
    total: int


class PlatformSearchResponse(BaseModel):
    """Results from platform content search"""

    results: List[Dict[str, Any]]
    total: int
    navigation: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response"""

    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IngestionRequest(BaseModel):
    """Request for ingesting data"""

    type: str = Field(
        ..., description="Type: platform_docs, nlp_knowledge, resources, legal"
    )
    data: List[Dict]


class IngestionResponse(BaseModel):
    """Response for data ingestion"""

    message: str
    count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatHistoryResponse(BaseModel):
    """Return chat history for a session"""

    session_id: str
    messages: List[Dict[str, str]]
    total: int
