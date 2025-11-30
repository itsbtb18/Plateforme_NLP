from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import ChatSession, ChatMessage
from app.services.groq_client import get_groq_client
from app.services.retrieval import get_retrieval_service
from app.schemas import ConversationRequest, ChatResponse, RetrievedDoc
from typing import List, Dict, Optional, Tuple
import logging
from langdetect import detect, LangDetectException
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatLogic:
    """Main chat logic orchestrating RAG pipeline"""
    
    def __init__(self):
        self.groq_client = get_groq_client()
        self.retrieval_service = get_retrieval_service()
    
    def detect_language(self, text: str) -> str:
        """Detect language of text (ar, en, fr)"""
        try:
            lang = detect(text)
            # Map to our supported languages
            if lang in ['ar', 'en', 'fr']:
                return lang
            # Default fallbacks
            if lang in ['es', 'it', 'pt']:
                return 'fr'
            return 'en'
        except LangDetectException:
            return 'en'
    
    async def handle_conversation(
        self,
        request: ConversationRequest,
        db: AsyncSession
    ) -> ChatResponse:
        """Handle conversation mode with RAG"""
        
        # Detect language
        language = self.detect_language(request.question)
        logger.info(f"Detected language: {language}")
        
        # Perform hybrid search
        retrieved_docs, primary_source = await self.retrieval_service.hybrid_search(
            query=request.question,
            db=db,
            user_country=request.user_country,
            user_city=request.user_city
        )
        
        # Build context from retrieved documents
        context = self._build_context(retrieved_docs)
        
        # Get chat history from database
        chat_history = await self._get_chat_history(request.session_id, db)
        
        # Generate answer with context
        if context:
            answer = await self.groq_client.generate_answer_with_context(
                question=request.question,
                context=context,
                language=language,
                chat_history=chat_history
            )
            source = primary_source if primary_source != "none" else "groq"
        else:
            # No relevant context found, use pure LLM
            answer = await self.groq_client.quick_answer(request.question, language)
            source = "groq"
        
        # Save to database
        await self._save_message(
            session_id=request.session_id,
            role="user",
            content=request.question,
            source=None,
            language=language,
            db=db
        )
        
        await self._save_message(
            session_id=request.session_id,
            role="assistant",
            content=answer,
            source=source,
            language=language,
            db=db
        )
        
        # Build response
        retrieved_docs_schema = [
            RetrievedDoc(
                id=doc['id'],
                title=doc.get('title', 'N/A'),
                content=doc['content'][:200] + "...",
                source=doc['source'],
                similarity=doc['similarity']
            )
            for doc in retrieved_docs[:3]
        ]
        
        return ChatResponse(
            answer=answer,
            source=source,
            session_id=request.session_id,
            lang=language,
            retrieved_docs=retrieved_docs_schema if retrieved_docs else None
        )
    
    async def handle_quick_query(
        self,
        question: str
    ) -> ChatResponse:
        """Handle quick question without context"""
        
        language = self.detect_language(question)
        answer = await self.groq_client.quick_answer(question, language)
        
        return ChatResponse(
            answer=answer,
            source="groq",
            session_id="quick_query",
            lang=language,
            retrieved_docs=None
        )
    
    async def handle_pdf_question(
        self,
        question: str,
        session_id: str,
        db: AsyncSession
    ) -> ChatResponse:
        """Handle question about uploaded PDF"""
        
        language = self.detect_language(question)
        
        # Get PDF context from session
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session or not session.pdf_context:
            raise ValueError("No PDF context found for this session")
        
        # Generate answer with PDF context
        answer = await self.groq_client.generate_answer_with_context(
            question=question,
            context=session.pdf_context[:10000],  # Limit context size
            language=language,
            chat_history=None
        )
        
        # Save to database
        await self._save_message(
            session_id=session_id,
            role="user",
            content=question,
            source="pdf",
            language=language,
            db=db
        )
        
        await self._save_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            source="pdf",
            language=language,
            db=db
        )
        
        return ChatResponse(
            answer=answer,
            source="pdf",
            session_id=session_id,
            lang=language,
            retrieved_docs=None
        )
    
    async def create_session(
        self,
        user_id: Optional[str],
        user_country: Optional[str],
        user_city: Optional[str],
        db: AsyncSession
    ) -> str:
        """Create new chat session"""
        
        session_id = str(uuid.uuid4())
        
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            user_country=user_country,
            user_city=user_city
        )
        
        db.add(session)
        await db.commit()
        
        logger.info(f"✅ Created session: {session_id}")
        return session_id
    
    async def end_session(self, session_id: str, db: AsyncSession):
        """End chat session (soft delete)"""
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            # We don't delete, just mark as ended
            session.last_activity = datetime.utcnow()
            await db.commit()
            logger.info(f"✅ Ended session: {session_id}")
    
    def _build_context(self, docs: List[Dict]) -> str:
        """Build context string from retrieved documents"""
        if not docs:
            return ""
        
        context_parts = []
        for i, doc in enumerate(docs[:5], 1):  # Top 5
            source_type = doc['source']
            title = doc.get('title', 'N/A')
            content = doc['content'][:500]  # Limit each doc
            
            context_parts.append(f"[Document {i} from {source_type}]\nTitle: {title}\nContent: {content}\n")
        
        return "\n---\n".join(context_parts)
    
    async def _get_chat_history(
        self,
        session_id: str,
        db: AsyncSession,
        limit: int = 6
    ) -> List[Dict[str, str]]:
        """Get recent chat history for context"""
        
        stmt = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(
            ChatMessage.created_at.desc()
        ).limit(limit)
        
        result = await db.execute(stmt)
        messages = result.scalars().all()
        
        # Reverse to get chronological order
        history = []
        for msg in reversed(messages):
            if msg.role in ["user", "assistant"]:
                history.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return history
    
    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: Optional[str],
        language: str,
        db: AsyncSession
    ):
        """Save chat message to database"""
        
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            source=source,
            language=language
        )
        
        db.add(message)
        await db.commit()

# Singleton instance
_chat_logic = None

def get_chat_logic() -> ChatLogic:
    """Get or create chat logic instance"""
    global _chat_logic
    if _chat_logic is None:
        _chat_logic = ChatLogic()
    return _chat_logic
