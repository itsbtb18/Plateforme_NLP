from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ARRAY, ForeignKey, Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class PlatformDoc(Base):
    """Documentation about the platform features and functionalities."""
    __tablename__ = "platform_docs"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100))
    language = Column(String(10), default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class NLPKnowledge(Base):
    """Arabic NLP knowledge base — concepts, terminology, techniques."""
    __tablename__ = "nlp_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), index=True, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    keywords = Column(ARRAY(String))
    difficulty = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Resource(Base):
    """Research resources: articles, projects, institutions, datasets, events."""
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), index=True, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(Text)
    description = Column(Text, nullable=False)
    tags = Column(ARRAY(String))
    country = Column(String(100))
    city = Column(String(100))
    author = Column(String(255))
    institution = Column(String(255))
    year = Column(Integer)
    relevance_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_resources_location", "country", "city"),
    )


class LegalDocument(Base):
    """Legal / regulatory knowledge base."""
    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    jurisdiction = Column(String(100), index=True)
    category = Column(String(100), index=True)
    content = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    source_reference = Column(Text)
    keywords = Column(ARRAY(String))
    effective_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserDocument(Base):
    """User-uploaded documents for per-session retrieval."""
    __tablename__ = "user_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True)
    session_id = Column(String(255), index=True, nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size_bytes = Column(Integer)
    raw_text = Column(Text)  # Extracted text stored for async processing
    total_chunks = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Individual chunks of user-uploaded documents (text only; vectors in Qdrant)."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("user_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("UserDocument", back_populates="chunks")


class ChatSession(Base):
    """User chat sessions for conversation tracking."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True)
    title = Column(String(255))
    user_country = Column(String(100))
    user_city = Column(String(100))
    preferred_language = Column(String(10))
    is_active = Column(Boolean, default=True)
    summary = Column(Text)
    pdf_context = Column(Text)
    pdf_filename = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat message history for each session."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(50))
    language = Column(String(10))
    retrieved_docs_count = Column(Integer, default=0)
    token_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_messages_session", "session_id", "created_at"),
    )
