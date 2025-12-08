from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ARRAY, Index
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db import Base
from app.config import get_settings

settings = get_settings()

class PlatformDoc(Base):
    """Documentation about the platform features and functionalities"""
    __tablename__ = "platform_docs"
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100))  # features, troubleshooting, modules, etc.
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_platform_docs_embedding', 'embedding', postgresql_using='ivfflat'),
    )

class NLPKnowledge(Base):
    """Arabic NLP knowledge base - concepts, terminology, techniques"""
    __tablename__ = "nlp_knowledge"
    
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), index=True, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(10), default="en")  # ar, en, fr
    keywords = Column(ARRAY(String))
    difficulty = Column(String(20))  # beginner, intermediate, advanced
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_nlp_knowledge_embedding', 'embedding', postgresql_using='ivfflat'),
    )

class Resource(Base):
    """Research resources: articles, projects, institutions, datasets, events"""
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), index=True, nullable=False)  # article, project, institution, dataset, tutorial, conference
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
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_resources_embedding', 'embedding', postgresql_using='ivfflat'),
        Index('idx_resources_location', 'country', 'city'),
    )

class ChatSession(Base):
    """User chat sessions for conversation tracking"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True)  # Django user ID
    user_country = Column(String(100))
    user_city = Column(String(100))
    pdf_context = Column(Text)  # Stored PDF content for PDF-based questions
    pdf_filename = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    """Chat message history for each session"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    source = Column(String(50))  # platform_docs, nlp_knowledge, resources, groq, hybrid
    language = Column(String(10))  # ar, en, fr
    retrieved_docs_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_chat_messages_session', 'session_id', 'created_at'),
    )
