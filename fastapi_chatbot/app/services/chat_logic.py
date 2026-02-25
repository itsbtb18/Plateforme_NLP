"""
Chat logic — pure RAG orchestration (v5.0 — Retrieval Strategy).

Pipeline per conversation turn:
  1. Classify intent  (query_classifier)
  2. Route retrieval   (query_router)
  3. Build context     (this module)
  4. Generate answer   (groq_client)
  5. Persist messages  (session_service)

Session CRUD, document management, and message storage are handled by
SessionService and DocumentService respectively.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import get_groq_client
from app.services.retrieval import (
    search_legal_documents,
    search_user_documents,
)
from app.services.classifier import get_query_classifier, QueryClassification
from app.services.router import get_query_router, RoutingResult
from app.services.memory import get_session_service
from app.schemas import ConversationRequest, ChatResponse, RetrievedDoc
from app.models import ChatSession, UserDocument
from sqlalchemy import select, func as sqlfunc
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ChatLogic:
    """RAG orchestration — classify → route → generate → persist.

    Delegates session management to SessionService.
    Delegates document management to DocumentService.
    """

    def __init__(self):
        self.groq = get_groq_client()            # LLM (isolated)
        self.classifier = get_query_classifier()  # Step 1-2
        self.router = get_query_router()          # Step 3
        self.sessions = get_session_service()     # PostgreSQL session ops

    # ------------------------------------------------------------------
    # Conversation handler (full RAG pipeline)
    # ------------------------------------------------------------------

    async def handle_conversation(
        self, request: ConversationRequest, db: AsyncSession,
    ) -> ChatResponse:
        # Check if the user actually has uploaded documents (not just a session)
        has_docs = False
        if request.user_id:
            doc_count = await db.execute(
                select(sqlfunc.count()).select_from(UserDocument).where(
                    UserDocument.user_id == request.user_id,
                    UserDocument.status == "completed",
                )
            )
            has_docs = (doc_count.scalar() or 0) > 0

        # Step 1-2: Detect language + classify intent
        classification = self.classifier.classify(
            request.question,
            has_session_docs=has_docs,
        )
        language = classification.language

        logger.info(
            "Classification: intent=%s lang=%s confidence=%.2f",
            classification.intent, language, classification.confidence,
        )

        # Step 3: Route to correct data source(s)
        routing: RoutingResult = await self.router.route(
            question=request.question,
            classification=classification,
            db=db,
            session_id=request.session_id,
            user_id=request.user_id,
            user_country=request.user_country,
            user_city=request.user_city,
        )

        # Step 4: Build context from routing result
        # Phase 9: Platform data (PostgreSQL facts) is labelled with higher
        # priority so the LLM knows to prefer it over semantic results.
        context = self._build_context(routing.retrieved_docs)

        if routing.platform_results:
            platform_ctx = self._build_platform_context(routing.platform_results)
            if platform_ctx:
                # Prepend platform data BEFORE semantic results so it appears first
                if context:
                    context = (
                        "=== ✅ Platform Data (verified facts from database) ===\n"
                        + platform_ctx
                        + "\n\n=== Semantic Search Results ===\n"
                        + context
                    )
                else:
                    context = (
                        "=== ✅ Platform Data (verified facts from database) ===\n"
                        + platform_ctx
                    )

        if routing.nav_hints and routing.nav_hints.get("suggestions"):
            nav_ctx = self._build_nav_context(routing.nav_hints)
            context = (context + "\n\n--- Navigation ---\n" + nav_ctx) if context else nav_ctx

        # Conversation memory
        chat_history = await self.sessions.get_recent_messages(request.session_id, db)
        session_summary = await self.sessions.get_summary(request.session_id, db)

        # Step 5: Groq reasoning & generation
        source = routing.primary_source
        if context and not routing.skip_retrieval:
            # Phase 9: pass source_type so Groq gets specialised rules
            logger.info(
                "RAG generation: source=%s context_len=%d docs=%d",
                source, len(context), len(routing.retrieved_docs),
            )
            answer = await self.groq.generate_answer_with_context(
                question=request.question,
                context=context,
                language=language,
                chat_history=chat_history,
                session_summary=session_summary,
                source_type=source,
            )
            if source == "none":
                source = "groq"
        else:
            logger.info(
                "Direct LLM (no retrieval): skip=%s context_empty=%s",
                routing.skip_retrieval, not context,
            )
            answer = await self.groq.quick_answer(request.question, language)
            source = "groq"

        # Step 6: Persist messages
        await self.sessions.save_message(request.session_id, "user", request.question, None, language, db)
        await self.sessions.save_message(
            request.session_id, "assistant", answer, source, language, db,
            retrieved_count=len(routing.retrieved_docs),
        )
        await self.sessions.auto_title(request.session_id, request.question, db)
        await self.sessions.maybe_trigger_summarisation(request.session_id, db)
        await self.sessions.update_language(request.session_id, language, db)

        return ChatResponse(
            answer=answer,
            source=source,
            session_id=request.session_id,
            lang=language,
            retrieved_docs=self._to_schema(routing.retrieved_docs),
            platform_results=routing.platform_results if routing.platform_results else None,
        )

    # ------------------------------------------------------------------
    # Quick query (no context / no session)
    # ------------------------------------------------------------------

    async def handle_quick_query(self, question: str, language: Optional[str] = None) -> ChatResponse:
        lang = language or self.classifier.classify(question).language
        answer = await self.groq.quick_answer(question, lang)
        return ChatResponse(
            answer=answer, source="groq",
            session_id="quick_query", lang=lang,
        )

    # ------------------------------------------------------------------
    # PDF question (legacy – uses raw pdf_context on session)
    # ------------------------------------------------------------------

    async def handle_pdf_question(
        self, question: str, session_id: str, db: AsyncSession,
    ) -> ChatResponse:
        language = self.classifier.classify(question).language

        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session or not session.pdf_context:
            raise ValueError("No PDF context found for this session")

        pdf_ctx = str(session.pdf_context)[:10000]
        chat_history = await self.sessions.get_recent_messages(session_id, db)
        session_summary = await self.sessions.get_summary(session_id, db)
        answer = await self.groq.generate_answer_with_context(
            question=question, context=pdf_ctx,
            language=language, chat_history=chat_history,
            session_summary=session_summary,
        )

        await self.sessions.save_message(session_id, "user", question, "pdf", language, db)
        await self.sessions.save_message(session_id, "assistant", answer, "pdf", language, db)

        return ChatResponse(
            answer=answer, source="pdf",
            session_id=session_id, lang=language,
        )

    # ------------------------------------------------------------------
    # User-document question (vector-searched chunks)
    # ------------------------------------------------------------------

    async def handle_user_doc_question(
        self, question: str, session_id: str, db: AsyncSession,
        document_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> ChatResponse:
        language = self.classifier.classify(question).language

        # Phase 7: owner_id is mandatory — users can ONLY retrieve their own docs
        docs = await search_user_documents(
            query=question, db=db,
            session_id=session_id,
            document_id=document_id,
            owner_id=user_id,
        )

        if not docs:
            # Phase 10 — Safety: do NOT fall back to general LLM.
            # Without owner-matched documents, answering with open-ended
            # knowledge could mislead the user into thinking the answer
            # came from their private document.
            _no_doc = {
                "ar": "لم أجد محتوى مطابقاً في مستنداتك. يرجى التأكد من رفع المستند وأنه تمت معالجته بنجاح.",
                "fr": "Aucun contenu correspondant n'a été trouvé dans vos documents. Veuillez vérifier que le document a été téléversé et traité avec succès.",
                "en": "No matching content was found in your documents. Please make sure the document has been uploaded and processed successfully.",
            }
            answer = _no_doc.get(language, _no_doc["en"])
            source = "none"
        else:
            context = self._build_context(docs)
            chat_history = await self.sessions.get_recent_messages(session_id, db)
            session_summary = await self.sessions.get_summary(session_id, db)
            answer = await self.groq.generate_answer_with_context(
                question=question, context=context,
                language=language, chat_history=chat_history,
                session_summary=session_summary,
                source_type="user_document",
            )
            source = "user_document"

        await self.sessions.save_message(session_id, "user", question, source, language, db)
        await self.sessions.save_message(session_id, "assistant", answer, source, language, db, retrieved_count=len(docs))

        return ChatResponse(
            answer=answer, source=source,
            session_id=session_id, lang=language,
            retrieved_docs=self._to_schema(docs),
        )

    # ------------------------------------------------------------------
    # Legal search + answer
    # ------------------------------------------------------------------

    async def handle_legal_question(
        self, question: str, db: AsyncSession,
        jurisdiction: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
    ) -> ChatResponse:
        lang = language or self.classifier.classify(question).language

        # Phase 6: pass language so same-language laws are prioritised
        docs = await search_legal_documents(
            query=question, db=db,
            jurisdiction=jurisdiction,
            category=category,
            language=lang,
        )

        if not docs:
            # Phase 10 — Safety: NEVER fall back to general LLM for legal
            # questions.  Without retrieved legal texts, the model could
            # hallucinate laws, provisions, or article numbers.
            _no_legal = {
                "ar": "لم أجد نصوصاً قانونية ذات صلة بسؤالك في قاعدة البيانات. لا يمكنني الإجابة على أسئلة قانونية بدون مصادر موثوقة.",
                "fr": "Je n'ai trouvé aucun texte juridique pertinent dans la base de données. Je ne peux pas répondre à des questions juridiques sans sources fiables.",
                "en": "I could not find any relevant legal texts in the database. I cannot answer legal questions without verified sources.",
            }
            answer = _no_legal.get(lang, _no_legal["en"])
            source = "none"
        else:
            context = self._build_context(docs)
            answer = await self.groq.generate_answer_with_context(
                question=question, context=context, language=lang,
                source_type="legal",
            )
            source = "legal"

        return ChatResponse(
            answer=answer, source=source,
            session_id="legal_query", lang=lang,
            retrieved_docs=self._to_schema(docs),
        )

    # ------------------------------------------------------------------
    # Internals (context formatting only — no DB, no sessions)
    # ------------------------------------------------------------------

    def _build_context(self, docs: List[Dict]) -> str:
        if not docs:
            return ""
        parts = []
        for i, doc in enumerate(docs[:5], 1):
            src = doc.get("source", "unknown")
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:600]
            sim = doc.get("similarity", 0.0)
            parts.append(
                f"[Document {i} | source: {src} | similarity: {sim:.2f}]\n"
                f"Title: {title}\n{content}\n"
            )
        return "\n---\n".join(parts)

    @staticmethod
    def _build_platform_context(results: List[Dict[str, Any]]) -> str:
        """Format platform query results as context for the LLM."""
        if not results:
            return ""
        parts = []
        for i, r in enumerate(results[:8], 1):
            rtype = r.get("type", "unknown")
            title = r.get("title") or r.get("name", "N/A")
            desc = r.get("description", "")[:200]
            url = r.get("url", "")
            extras = []
            for key in ("document_type", "field", "level", "event_type",
                        "institution_type", "status", "language",
                        "start_date", "end_date", "journal", "doi",
                        "city", "country", "website", "author"):
                val = r.get(key)
                if val:
                    extras.append(f"{key}: {val}")
            extra_str = " | ".join(extras)
            url_line = f"\nLink: {url}" if url else ""
            parts.append(
                f"[Platform item {i} | type: {rtype}]\n"
                f"Title: {title}\n{desc}\n{extra_str}{url_line}"
            )
        return "\n---\n".join(parts)

    @staticmethod
    def _build_nav_context(nav_hints: Dict[str, Any]) -> str:
        """Format navigation hints for the LLM."""
        suggestions = nav_hints.get("suggestions", [])
        if not suggestions:
            return ""
        lines = ["The user may be looking for these platform sections:"]
        for s in suggestions:
            lines.append(f"  • {s.get('section', '')} — {s.get('url', '')}")
        return "\n".join(lines)

    @staticmethod
    def _to_schema(docs: List[Dict]) -> Optional[List[RetrievedDoc]]:
        if not docs:
            return None
        return [
            RetrievedDoc(
                id=d.get("id", 0),
                title=d.get("title", "N/A"),
                content=d.get("content", "")[:200] + "...",
                source=d.get("source", "unknown"),
                similarity=d.get("similarity", 0.0),
            )
            for d in docs[:5]
        ]


# Singleton
_chat_logic = None


def get_chat_logic() -> ChatLogic:
    global _chat_logic
    if _chat_logic is None:
        _chat_logic = ChatLogic()
    return _chat_logic
