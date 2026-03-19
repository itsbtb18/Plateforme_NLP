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
from app.services.llm.client import GroqClient
from app.services.retrieval import (
    search_legal_documents,
    search_user_documents,
)
from app.services.classifier import get_query_classifier, QueryClassification
from app.services.router import get_query_router, RoutingResult
from app.services.memory import get_session_service
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_DOCUMENT_CHUNKS
from app.services.retrieval.filters import build_user_doc_filter
from app.schemas import ConversationRequest, ChatResponse, RetrievedDoc, EntityExplainRequest
from app.models import ChatSession, UserDocument
from sqlalchemy import select, func as sqlfunc
from typing import List, Dict, Optional, Any, AsyncGenerator
import logging

logger = logging.getLogger(__name__)


class ChatLogic:
    """RAG orchestration — classify → route → generate → persist.

    Delegates session management to SessionService.
    Delegates document management to DocumentService.
    """

    def __init__(self):
        self.groq = get_groq_client()  # LLM (isolated)
        self.classifier = get_query_classifier()  # Step 1-2
        self.router = get_query_router()  # Step 3
        self.sessions = get_session_service()  # PostgreSQL session ops

    # ------------------------------------------------------------------
    # Conversation handler (full RAG pipeline)
    # ------------------------------------------------------------------

    async def handle_conversation(
        self,
        request: ConversationRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        # Check if the user actually has uploaded documents (not just a session)
        has_docs = False
        if request.user_id:
            doc_count = await db.execute(
                select(sqlfunc.count())
                .select_from(UserDocument)
                .where(
                    UserDocument.user_id == request.user_id,
                    UserDocument.status == "completed",
                )
            )
            has_docs = (doc_count.scalar() or 0) > 0

        # Phase 4.1: Load session row for document-session state
        session_row: ChatSession | None = None
        if request.session_id:
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.session_id == request.session_id
                )
            )
            session_row = result.scalars().first()

        # Step 1-2: Detect language + classify intent
        classification = self.classifier.classify(
            request.question,
            has_session_docs=has_docs,
        )
        language = classification.language

        # ── Phase 4.1: Document Session Persistence ──────────────────
        # Maintains a sticky "document mode" across turns so follow-up
        # questions like "explain more" or "how it impacts NLP" stay
        # routed to the user's uploaded document content.
        #
        # State is stored on ChatSession:
        #   active_document_session  (bool)
        #   active_document_id       (str | None)
        #   low_doc_similarity_streak (int)  — auto-deactivation counter
        #
        # Flow:
        #   1. Explicit deactivation?  → clear session, classify normally
        #   2. Active session?         → force document_query
        #      2a. Probe similarity    → if < 0.30, bump streak
        #      2b. streak >= 3         → auto-deactivate
        #   3. Explicit activation?    → activate session, force document_query
        #   4. Fallback               → Phase 4 dominance check (one-shot)

        _doc_session_handled = False

        if session_row and has_docs and request.user_id:
            # ── 1. Deactivation check ────────────────────────────────
            if (
                session_row.active_document_session
                and self._is_document_deactivation(request.question)
            ):
                session_row.active_document_session = False
                session_row.active_document_id = None
                session_row.low_doc_similarity_streak = 0
                logger.info(
                    "Document session DEACTIVATED (explicit): session=%s",
                    request.session_id,
                )
                # Let classification proceed normally (no override)
                _doc_session_handled = True

            # ── 2. Active session → stay in document mode ────────────
            elif session_row.active_document_session:
                doc_score = self._check_document_dominance(
                    request.question, owner_id=request.user_id,
                )
                if doc_score < 0.30:
                    streak = (session_row.low_doc_similarity_streak or 0) + 1
                    session_row.low_doc_similarity_streak = streak
                    logger.debug(
                        "Document session low-similarity streak: %d "
                        "(score=%.3f)", streak, doc_score,
                    )
                    if streak >= 3:
                        # Auto-deactivate after 3 consecutive low-sim turns
                        session_row.active_document_session = False
                        session_row.active_document_id = None
                        session_row.low_doc_similarity_streak = 0
                        logger.info(
                            "Document session AUTO-DEACTIVATED "
                            "(3 low-sim turns): session=%s",
                            request.session_id,
                        )
                        _doc_session_handled = True
                    else:
                        # Still in document mode despite low sim
                        classification = QueryClassification(
                            intent="document_query",
                            language=language,
                            confidence=max(doc_score, 0.50),
                            qdrant_collections=["document_chunks"],
                            qdrant_type_filter="document",
                        )
                        _doc_session_handled = True
                else:
                    # Good similarity — reset streak, stay in doc mode
                    session_row.low_doc_similarity_streak = 0
                    classification = QueryClassification(
                        intent="document_query",
                        language=language,
                        confidence=doc_score,
                        qdrant_collections=["document_chunks"],
                        qdrant_type_filter="document",
                    )
                    _doc_session_handled = True
                    logger.debug(
                        "Document session CONTINUES: score=%.3f",
                        doc_score,
                    )

            # ── 3. Activation check ──────────────────────────────────
            elif self._is_document_activation(request.question):
                session_row.active_document_session = True
                session_row.active_document_id = None  # could be refined later
                session_row.low_doc_similarity_streak = 0
                classification = QueryClassification(
                    intent="document_query",
                    language=language,
                    confidence=0.95,
                    qdrant_collections=["document_chunks"],
                    qdrant_type_filter="document",
                )
                _doc_session_handled = True
                logger.info(
                    "Document session ACTIVATED: session=%s",
                    request.session_id,
                )

        # ── 4. Fallback: Phase 4 one-shot dominance (no session yet) ─
        if (
            not _doc_session_handled
            and has_docs
            and request.user_id
            and classification.intent != "document_query"
        ):
            skip_dominance = (
                self._is_generic_conceptual(request.question)
                and not self._has_document_reference(request.question)
            )
            if skip_dominance:
                logger.debug(
                    "Document dominance skipped: generic conceptual query"
                )
            else:
                doc_score = self._check_document_dominance(
                    request.question, owner_id=request.user_id,
                )
                if doc_score >= 0.65:
                    logger.info(
                        "Document dominance triggered: score=%.3f, "
                        "overriding %s → document_query",
                        doc_score, classification.intent,
                    )
                    classification = QueryClassification(
                        intent="document_query",
                        language=language,
                        confidence=doc_score,
                        qdrant_collections=["document_chunks"],
                        qdrant_type_filter="document",
                    )
                    # Also activate session for subsequent turns
                    if session_row:
                        session_row.active_document_session = True
                        session_row.active_document_id = None
                        session_row.low_doc_similarity_streak = 0

        logger.info(
            "Classification: intent=%s lang=%s confidence=%.2f",
            classification.intent,
            language,
            classification.confidence,
        )

        # Phase 10: LLM fallback for ambiguous classifications
        if classification.confidence <= 0.60 and not _doc_session_handled:
            # Get top-2 intents for disambiguation
            scores = self.classifier._score_all_intents(
                request.question, has_session_docs=has_docs,
            )
            # If all scores are 0, the classifier intentionally defaulted
            # to conceptual_question — don't let LLM override that.
            if any(v > 0 for v in scores.values()):
                top_2 = sorted(scores, key=scores.get, reverse=True)[:2]
                resolved = await self.classifier.llm_resolve_ambiguity(
                    request.question, language, top_2,
                )
                if resolved and resolved != classification.intent:
                    logger.info(
                        "LLM reclassified: %s → %s", classification.intent, resolved,
                    )
                    classification = self.classifier._build_classification(
                        resolved, language, 0.80,
                    )
                    if resolved == "platform_query":
                        from app.services.classifier.patterns import extract_resource_type
                        classification.detected_resource_type = extract_resource_type(
                            request.question
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
            user_email=getattr(request, "user_email", None),
        )

        # Step 4: Build context from routing result
        # Phase 9: Platform data (PostgreSQL facts) is labelled with higher
        # priority so the LLM knows to prefer it over semantic results.
        context = self._build_context(routing.retrieved_docs)

        # Inject current user profile so the LLM knows who is asking
        # Only inject for intents that genuinely need it (user_query,
        # metadata_query).  For everything else (greetings, conceptual
        # questions, general knowledge, etc.) the profile is unnecessary
        # and can cause the LLM to proactively reveal the user's name.
        _profile_intents = {"user_query", "metadata_query"}
        user_ctx = ""
        if classification.intent in _profile_intents:
            user_ctx = self._build_user_context(request)
        logger.info(
            "User profile injection: user_name=%s, user_email=%s, ctx_len=%d",
            getattr(request, "user_name", None),
            getattr(request, "user_email", None),
            len(user_ctx) if user_ctx else 0,
        )
        if user_ctx:
            context = (
                (
                    "[User Profile]\n"
                    + user_ctx
                    + "\n\n"
                    + context
                )
                if context
                else (
                    "[User Profile]\n"
                    + user_ctx
                )
            )

        # Phase 5: Entity cards ONLY for direct platform queries.
        # No cards during conceptual explanations, user queries, or
        # metadata queries — only when the user explicitly asks about
        # courses, tools, institutions, resources, etc.
        _card_intents = {"platform_query"}
        if routing.platform_results and classification.intent in _card_intents:
            real_results = [r for r in routing.platform_results if r.get("type") != "no_data"]
            platform_ctx = self._build_platform_context(real_results) if real_results else ""
            if platform_ctx:
                # Prepend platform data BEFORE other results so it appears first
                if context:
                    context = (
                        "[Verified Data]\n"
                        + platform_ctx
                        + "\n\n[Additional Context]\n"
                        + context
                    )
                else:
                    context = (
                        "[Verified Data]\n"
                        + platform_ctx
                    )

        if routing.nav_hints and routing.nav_hints.get("suggestions"):
            nav_ctx = self._build_nav_context(routing.nav_hints)
            context = (
                (context + "\n\n--- Navigation ---\n" + nav_ctx) if context else nav_ctx
            )

        # Conversation memory
        chat_history = await self.sessions.get_recent_messages(request.session_id, db)
        session_summary = await self.sessions.get_summary(request.session_id, db)

        # Step 5: Groq reasoning & generation
        source = routing.primary_source
        # If we have context (including user profile), always use RAG path
        # so the LLM can see the user's identity even for general questions
        if context and (not routing.skip_retrieval or user_ctx):
            # Phase 9: pass source_type so Groq gets specialised rules
            logger.info(
                "RAG generation: source=%s context_len=%d docs=%d",
                source,
                len(context),
                len(routing.retrieved_docs),
            )
            answer = await self.groq.generate_answer_with_context(
                question=request.question,
                context=context,
                language=language,
                chat_history=chat_history,
                session_summary=session_summary,
                source_type=source,
                username=getattr(request, "user_name", None),
            )
            # If RAG returned a fallback (e.g. rate-limit), retry without
            # context so the conversation is never blocked.
            if GroqClient.is_fallback(answer):
                logger.warning(
                    "RAG answer was fallback — retrying via quick_answer "
                    "(source=%s)", source,
                )
                answer = await self.groq.quick_answer(
                    request.question, language,
                    username=getattr(request, "user_name", None),
                )
                source = "groq"
            if source == "none":
                source = "groq"
        else:
            logger.info(
                "Direct LLM (no retrieval): skip=%s context_empty=%s",
                routing.skip_retrieval,
                not context,
            )
            answer = await self.groq.quick_answer(request.question, language, username=getattr(request, "user_name", None))
            source = "groq"

        # Step 6: Persist messages
        await self.sessions.save_message(
            request.session_id, "user", request.question, None, language, db
        )
        await self.sessions.save_message(
            request.session_id,
            "assistant",
            answer,
            source,
            language,
            db,
            retrieved_count=len(routing.retrieved_docs),
        )
        await self.sessions.auto_title(request.session_id, request.question, db)
        await self.sessions.maybe_trigger_summarisation(request.session_id, db)
        await self.sessions.update_language(request.session_id, language, db)

        # Phase 5: Only return entity cards for direct platform queries
        show_cards = (
            [c for c in routing.platform_results if c.get("type") != "no_data"]
            if classification.intent in _card_intents and routing.platform_results
            else None
        )
        if show_cards is not None and len(show_cards) == 0:
            show_cards = None
        return ChatResponse(
            answer=answer,
            source=source,
            session_id=request.session_id,
            lang=language,
            retrieved_docs=self._to_schema(routing.retrieved_docs),
            platform_results=show_cards or None,
        )

    async def handle_conversation_stream(
        self,
        request: ConversationRequest,
        db: AsyncSession,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream conversation tokens as they arrive (SSE-style)."""
        has_docs = False
        if request.user_id:
            doc_count = await db.execute(
                select(sqlfunc.count())
                .select_from(UserDocument)
                .where(
                    UserDocument.user_id == request.user_id,
                    UserDocument.status == "completed",
                )
            )
            has_docs = (doc_count.scalar() or 0) > 0

        session_row: ChatSession | None = None
        if request.session_id:
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.session_id == request.session_id
                )
            )
            session_row = result.scalars().first()

        classification = self.classifier.classify(
            request.question,
            has_session_docs=has_docs,
        )
        language = classification.language

        _doc_session_handled = False
        if session_row and has_docs and request.user_id:
            if (
                session_row.active_document_session
                and self._is_document_deactivation(request.question)
            ):
                session_row.active_document_session = False
                session_row.active_document_id = None
                session_row.low_doc_similarity_streak = 0
                _doc_session_handled = True
            elif session_row.active_document_session:
                doc_score = self._check_document_dominance(
                    request.question, owner_id=request.user_id,
                )
                if doc_score < 0.30:
                    streak = (session_row.low_doc_similarity_streak or 0) + 1
                    session_row.low_doc_similarity_streak = streak
                    if streak >= 3:
                        session_row.active_document_session = False
                        session_row.active_document_id = None
                        session_row.low_doc_similarity_streak = 0
                        _doc_session_handled = True
                    else:
                        classification = QueryClassification(
                            intent="document_query",
                            language=language,
                            confidence=max(doc_score, 0.50),
                            qdrant_collections=["document_chunks"],
                            qdrant_type_filter="document",
                        )
                        _doc_session_handled = True
                else:
                    session_row.low_doc_similarity_streak = 0
                    classification = QueryClassification(
                        intent="document_query",
                        language=language,
                        confidence=doc_score,
                        qdrant_collections=["document_chunks"],
                        qdrant_type_filter="document",
                    )
                    _doc_session_handled = True
            elif self._is_document_activation(request.question):
                session_row.active_document_session = True
                session_row.active_document_id = None
                session_row.low_doc_similarity_streak = 0
                classification = QueryClassification(
                    intent="document_query",
                    language=language,
                    confidence=0.95,
                    qdrant_collections=["document_chunks"],
                    qdrant_type_filter="document",
                )
                _doc_session_handled = True

        if (
            not _doc_session_handled
            and has_docs
            and request.user_id
            and classification.intent != "document_query"
        ):
            skip_dominance = (
                self._is_generic_conceptual(request.question)
                and not self._has_document_reference(request.question)
            )
            if not skip_dominance:
                doc_score = self._check_document_dominance(
                    request.question, owner_id=request.user_id,
                )
                if doc_score >= 0.65:
                    classification = QueryClassification(
                        intent="document_query",
                        language=language,
                        confidence=doc_score,
                        qdrant_collections=["document_chunks"],
                        qdrant_type_filter="document",
                    )
                    if session_row:
                        session_row.active_document_session = True
                        session_row.active_document_id = None
                        session_row.low_doc_similarity_streak = 0

        if classification.confidence <= 0.60 and not _doc_session_handled:
            scores = self.classifier._score_all_intents(
                request.question, has_session_docs=has_docs,
            )
            if any(v > 0 for v in scores.values()):
                top_2 = sorted(scores, key=scores.get, reverse=True)[:2]
                resolved = await self.classifier.llm_resolve_ambiguity(
                    request.question, language, top_2,
                )
                if resolved and resolved != classification.intent:
                    classification = self.classifier._build_classification(
                        resolved, language, 0.80,
                    )
                    if resolved == "platform_query":
                        from app.services.classifier.patterns import extract_resource_type
                        classification.detected_resource_type = extract_resource_type(
                            request.question
                        )

        routing: RoutingResult = await self.router.route(
            question=request.question,
            classification=classification,
            db=db,
            session_id=request.session_id,
            user_id=request.user_id,
            user_country=request.user_country,
            user_city=request.user_city,
            user_email=getattr(request, "user_email", None),
        )

        context = self._build_context(routing.retrieved_docs)
        _profile_intents = {"user_query", "metadata_query"}
        user_ctx = ""
        if classification.intent in _profile_intents:
            user_ctx = self._build_user_context(request)
        if user_ctx:
            context = (
                ("[User Profile]\n" + user_ctx + "\n\n" + context)
                if context
                else ("[User Profile]\n" + user_ctx)
            )

        _card_intents = {"platform_query"}
        if routing.platform_results and classification.intent in _card_intents:
            real_results = [r for r in routing.platform_results if r.get("type") != "no_data"]
            platform_ctx = self._build_platform_context(real_results) if real_results else ""
            if platform_ctx:
                context = (
                    ("[Verified Data]\n" + platform_ctx + "\n\n[Additional Context]\n" + context)
                    if context
                    else ("[Verified Data]\n" + platform_ctx)
                )

        if routing.nav_hints and routing.nav_hints.get("suggestions"):
            nav_ctx = self._build_nav_context(routing.nav_hints)
            context = (
                (context + "\n\n--- Navigation ---\n" + nav_ctx) if context else nav_ctx
            )

        chat_history = await self.sessions.get_recent_messages(request.session_id, db)
        session_summary = await self.sessions.get_summary(request.session_id, db)

        source = routing.primary_source
        answer = ""

        if context and (not routing.skip_retrieval or user_ctx):
            async for chunk in self.groq.generate_answer_with_context_stream(
                question=request.question,
                context=context,
                language=language,
                chat_history=chat_history,
                session_summary=session_summary,
                source_type=source,
                username=getattr(request, "user_name", None),
            ):
                answer += chunk
                yield {"delta": chunk}
            if GroqClient.is_fallback(answer):
                answer = ""
                source = "groq"
                async for chunk in self.groq.quick_answer_stream(
                    request.question, language,
                    username=getattr(request, "user_name", None),
                ):
                    answer += chunk
                    yield {"delta": chunk}
            if source == "none":
                source = "groq"
        else:
            source = "groq"
            async for chunk in self.groq.quick_answer_stream(
                request.question, language,
                username=getattr(request, "user_name", None),
            ):
                answer += chunk
                yield {"delta": chunk}

        await self.sessions.save_message(
            request.session_id, "user", request.question, None, language, db
        )
        await self.sessions.save_message(
            request.session_id,
            "assistant",
            answer,
            source,
            language,
            db,
            retrieved_count=len(routing.retrieved_docs),
        )
        await self.sessions.auto_title(request.session_id, request.question, db)
        await self.sessions.maybe_trigger_summarisation(request.session_id, db)
        await self.sessions.update_language(request.session_id, language, db)

        show_cards = (
            [c for c in routing.platform_results if c.get("type") != "no_data"]
            if classification.intent in _card_intents and routing.platform_results
            else None
        )
        if show_cards is not None and len(show_cards) == 0:
            show_cards = None

        retrieved_schema = self._to_schema(routing.retrieved_docs)
        yield {
            "done": True,
            "answer": answer,
            "source": source,
            "session_id": request.session_id,
            "lang": language,
            "retrieved_docs": [d.model_dump() if hasattr(d, "model_dump") else d for d in (retrieved_schema or [])],
            "platform_results": show_cards,
        }

    # ------------------------------------------------------------------
    # Quick query (no context / no session)
    # ------------------------------------------------------------------

    async def handle_quick_query(
        self, question: str, language: Optional[str] = None
    ) -> ChatResponse:
        lang = language or self.classifier.classify(question).language
        answer = await self.groq.quick_answer(question, lang)
        return ChatResponse(
            answer=answer,
            source="groq",
            session_id="quick_query",
            lang=lang,
        )

    # ------------------------------------------------------------------
    # PDF question (legacy – uses raw pdf_context on session)
    # ------------------------------------------------------------------

    async def handle_pdf_question(
        self,
        question: str,
        session_id: str,
        db: AsyncSession,
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
            question=question,
            context=pdf_ctx,
            language=language,
            chat_history=chat_history,
            session_summary=session_summary,
        )

        await self.sessions.save_message(
            session_id, "user", question, "pdf", language, db
        )
        await self.sessions.save_message(
            session_id, "assistant", answer, "pdf", language, db
        )

        return ChatResponse(
            answer=answer,
            source="pdf",
            session_id=session_id,
            lang=language,
        )

    # ------------------------------------------------------------------
    # User-document question (vector-searched chunks)
    # ------------------------------------------------------------------

    async def handle_user_doc_question(
        self,
        question: str,
        session_id: str,
        db: AsyncSession,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        user_id: Optional[str] = None,
    ) -> ChatResponse:
        language = self.classifier.classify(question).language

        # Phase 7: owner_id is mandatory — users can ONLY retrieve their own docs
        # Phase 12: use higher top_k for better multi-document coverage
        docs = await search_user_documents(
            query=question,
            db=db,
            session_id=session_id,
            document_id=document_id,
            document_ids=document_ids,
            owner_id=user_id,
            top_k=8,
        )

        if not docs:
            # No matching chunks — fall back to general knowledge so the
            # conversation is never blocked by retrieval failure.
            logger.info(
                "No user-doc chunks found — falling back to quick_answer"
            )
            answer = await self.groq.quick_answer(question, language)
            source = "groq"
        else:
            context = self._build_context(docs)
            chat_history = await self.sessions.get_recent_messages(session_id, db)
            session_summary = await self.sessions.get_summary(session_id, db)
            answer = await self.groq.generate_answer_with_context(
                question=question,
                context=context,
                language=language,
                chat_history=chat_history,
                session_summary=session_summary,
                source_type="user_document",
            )
            # If RAG returned a fallback, retry without context
            if GroqClient.is_fallback(answer):
                logger.warning(
                    "User-doc RAG fallback — retrying via quick_answer"
                )
                answer = await self.groq.quick_answer(question, language)
                source = "groq"
            else:
                source = "user_document"

        await self.sessions.save_message(
            session_id, "user", question, source, language, db
        )
        await self.sessions.save_message(
            session_id,
            "assistant",
            answer,
            source,
            language,
            db,
            retrieved_count=len(docs),
        )

        return ChatResponse(
            answer=answer,
            source=source,
            session_id=session_id,
            lang=language,
            retrieved_docs=self._to_schema(docs),
        )

    # ------------------------------------------------------------------
    # Platform entity explain (skip classifier — direct context → LLM)
    # ------------------------------------------------------------------

    async def handle_entity_explain(
        self,
        request: EntityExplainRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        """Generate a rich explanation of a platform entity.

        Skips intent classification entirely — the entity metadata IS the
        context.  Optionally enriches with Qdrant knowledge if available.
        """
        lang = request.language or self.classifier.classify(
            request.entity_title
        ).language

        # Assemble entity context as verified data
        meta = request.entity_metadata or {}
        ctx_parts = [
            f"[Verified Data — Platform {request.entity_type}]",
            f"Title: {request.entity_title}",
        ]
        if request.entity_description:
            ctx_parts.append(f"Description: {request.entity_description[:3000]}")
        for key, val in meta.items():
            if val:
                ctx_parts.append(f"{key}: {val}")
        entity_context = "\n".join(ctx_parts)

        # Optional: enrich with related NLP knowledge from Qdrant
        extra_context = ""
        try:
            routing = await self.router.route(
                request.entity_title,
                QueryClassification(
                    intent="nlp_knowledge",
                    language=lang,
                    confidence=0.9,
                ),
            )
            if routing.results:
                extra_context = self._build_context(routing.results)
        except Exception:
            logger.debug("Entity explain: optional Qdrant enrichment failed", exc_info=True)

        # Combine contexts
        full_context = entity_context
        if extra_context:
            full_context += "\n\n[Additional Context]\n" + extra_context

        # Build the implicit question
        question = (
            f"Explain what '{request.entity_title}' is. "
            f"Provide a helpful overview of this {request.entity_type}, "
            f"its purpose, key features, and how it can be useful."
        )

        chat_history = await self.sessions.get_recent_messages(
            request.session_id, db
        )

        answer = await self.groq.generate_answer_with_context(
            question=question,
            context=full_context,
            language=lang,
            chat_history=chat_history,
            source_type="platform",
        )

        source = "platform"
        if GroqClient.is_fallback(answer):
            answer = await self.groq.quick_answer(question, lang)
            source = "groq"

        # Persist messages
        await self.sessions.save_message(
            request.session_id, "user", question, source, lang, db
        )
        await self.sessions.save_message(
            request.session_id, "assistant", answer, source, lang, db
        )

        return ChatResponse(
            answer=answer,
            source=source,
            session_id=request.session_id,
            lang=lang,
        )

    # ------------------------------------------------------------------
    # Legal search + answer
    # ------------------------------------------------------------------

    async def handle_legal_question(
        self,
        question: str,
        db: AsyncSession,
        jurisdiction: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
    ) -> ChatResponse:
        lang = language or self.classifier.classify(question).language

        # Phase 6: pass language so same-language laws are prioritised
        docs = await search_legal_documents(
            query=question,
            db=db,
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
                question=question,
                context=context,
                language=lang,
                source_type="legal",
            )
            source = "legal"

        return ChatResponse(
            answer=answer,
            source=source,
            session_id="legal_query",
            lang=lang,
            retrieved_docs=self._to_schema(docs),
        )

    # ------------------------------------------------------------------
    # Internals (context formatting only — no DB, no sessions)
    # ------------------------------------------------------------------

    def _build_context(self, docs: List[Dict]) -> str:
        """Build clean context for LLM — no metadata, no scores, no labels.

        Quality threshold: results below 0.60 similarity are dropped.
        If ALL results are below threshold, returns empty string so the
        LLM falls back to general knowledge.
        """
        if not docs:
            return ""

        quality_threshold = 0.60

        # Check if these are user-uploaded document chunks
        is_user_doc = any(d.get("source") == "user_document" for d in docs)

        if is_user_doc:
            # Group chunks by filename for clearer LLM context
            from collections import defaultdict

            by_file: dict[str, list[str]] = defaultdict(list)
            for doc in docs[:10]:
                fname = doc.get("title", "Untitled")
                content = doc.get("content", "")[:800]
                by_file[fname].append(content)

            parts = []
            for fname, chunks in by_file.items():
                combined = "\n\n".join(chunks)
                parts.append(f"[File: {fname}]\n{combined}\n")
            return "\n---\n".join(parts)

        # Filter by quality threshold — drop weak results
        quality_docs = [
            d for d in docs if d.get("similarity", 0) >= quality_threshold
        ]
        if not quality_docs:
            return ""

        # Clean content only — no metadata, scores, titles, or source labels
        parts = []
        for doc in quality_docs[:5]:
            content = doc.get("content", "")[:800]
            if content.strip():
                parts.append(content.strip())
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _build_user_context(request) -> str:
        """Build a concise text block describing the current logged-in user.

        NOTE: email is deliberately EXCLUDED for privacy/security.
        """
        parts: list[str] = []
        if getattr(request, "user_name", None):
            parts.append(f"Name: {request.user_name}")
        if getattr(request, "user_bio", None):
            parts.append(f"Bio: {request.user_bio}")
        if getattr(request, "user_institution", None):
            parts.append(f"Institution: {request.user_institution}")
        if getattr(request, "user_speciality", None):
            parts.append(f"Speciality: {request.user_speciality}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Phase 4.1 — Document session activation / deactivation detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_document_activation(question: str) -> bool:
        """Return True if the user is explicitly asking to work with a document.

        Triggers on phrases like:
          - "analyze this document"
          - "summarize Yanis1.pdf"
          - "explain this paper"
          - "review my file"
        """
        import re
        q = question.strip()
        return bool(re.search(
            r"(?:"
            # EN activation phrases
            r"\b(?:analyze|analyse|summarize|summarise|explain|review|read|open|use|look at|examine)"
            r"\s+(?:this |my |the )?(?:document|paper|file|pdf|report|text|upload)"
            r"|\b(?:document|paper|file|pdf|report)\b.*\b(?:analyze|summarize|explain|review)\b"
            # Filename references (e.g. "summarize Yanis1.pdf")
            r"|\b(?:analyze|analyse|summarize|summarise|explain|review|read|open|use)\s+\S+\.(?:pdf|docx?|txt|csv|xlsx?)\b"
            # FR activation phrases
            r"|\b(?:analyser?|résumer?|expliquer?|examiner?|lire|ouvrir|utiliser)"
            r"\s+(?:ce |mon |le |la )?(?:document|fichier|texte|rapport|article)"
            r"|\b(?:analyser?|résumer?|expliquer?|examiner?)\s+\S+\.(?:pdf|docx?|txt)\b"
            # AR activation phrases
            r"|\b(?:حلل|لخص|اشرح|راجع|اقرأ|افتح|استخدم)\s+(?:هذا |هذه )?(?:المستند|الملف|الوثيقة|النص|المقال|التقرير)"
            r")",
            q,
            re.I,
        ))

    @staticmethod
    def _is_document_deactivation(question: str) -> bool:
        """Return True if the user explicitly wants to leave document mode.

        Triggers on phrases like:
          - "new topic", "unrelated question"
          - "forget document", "stop using document"
          - "general question", "change subject"
        """
        import re
        q = question.strip()
        return bool(re.search(
            r"(?:"
            # EN deactivation phrases
            r"\b(?:new topic|change (?:topic|subject)|unrelated question|general question)"
            r"|\b(?:forget|stop using|ignore|close|leave|exit|done with)\s+(?:the |this |my )?(?:document|paper|file|pdf)"
            r"|\b(?:stop|exit|leave|end)\s+document\s*(?:mode|session)?"
            # FR deactivation phrases
            r"|\b(?:nouveau sujet|changer de sujet|question générale|question sans rapport)"
            r"|\b(?:oublier|arrêter|ignorer|fermer|quitter)\s+(?:le |ce |mon )?(?:document|fichier)"
            # AR deactivation phrases
            r"|\b(?:موضوع جديد|سؤال عام|غير (?:ذي صلة|متعلق))"
            r"|\b(?:أغلق|انسَ|توقف عن|اترك)\s+(?:المستند|الملف|الوثيقة)"
            r")",
            q,
            re.I,
        ))

    @staticmethod
    def _is_generic_conceptual(question: str) -> bool:
        """Return True if the question is a generic conceptual/definitional
        query that should NOT trigger document dominance.

        Matches patterns like:
          - "what is X" / "what are X"
          - "define X" / "explain X"
          - "difference between X and Y"
          - "how does X work"
        """
        import re
        q = question.strip()
        return bool(re.search(
            r"(?:"
            r"\b(?:what|qu(?:'|\u2019)?(?:est[- ]ce qu(?:'|\u2019)?|el(?:le)?s? (?:est|sont)))\b"
            r"|\b(?:what(?:'s| is| are))\s"
            r"|\b(?:define|explain|describe|clarify)\s"
            r"|\b(?:d[eé]finir|expliquer|d[eé]crire)\s"
            r"|\b(?:ما (?:هو|هي|هم|معنى)|عرّف|اشرح)\b"
            r"|\bdifference(?:s)?\s+(?:between|entre)\b"
            r"|\b(?:الفرق بين)\b"
            r"|\bhow does\b.*\bwork\b"
            r"|\bcomment fonctionne\b"
            r"|\bكيف يعمل\b"
            r")",
            q,
            re.I,
        ))

    @staticmethod
    def _has_document_reference(question: str) -> bool:
        """Return True if the question refers to uploaded document content.

        Detects:
          - Explicit references: "in my document", "in this paper", etc.
          - Pronoun references:  "he", "she", "this person", "the author"
          - Contextual anchors:  "according to", "based on the text"
        """
        import re
        q = question.lower().strip()
        return bool(re.search(
            r"(?:"
            # Explicit document references (EN/FR/AR)
            r"\b(?:in (?:my|the|this) (?:document|file|paper|pdf|report|text|upload))"
            r"|\b(?:from (?:my|the|this) (?:document|file|paper|pdf|report|text))"
            r"|\b(?:dans (?:mon|le|ce) (?:document|fichier|texte|rapport))"
            r"|\b(?:في (?:المستند|الملف|الوثيقة|النص|المقال|التقرير|ملفي|مستندي))"
            # Contextual anchors
            r"|\b(?:according to|based on|as (?:stated|mentioned|described) in)"
            r"|\b(?:selon|d'après|comme mentionné)"
            r"|\b(?:حسب|وفقاً|كما (?:ذُكر|ورد))"
            # Pronoun / entity references suggesting document content
            r"|\b(?:the author|this person|the researcher|the speaker)"
            r"|\b(?:l'auteur|cette personne|le chercheur)"
            r"|\b(?:الكاتب|المؤلف|الباحث|هذا الشخص)"
            # Page/section references
            r"|\b(?:page|section|chapter|paragraph|table|figure)\s*\d"
            r"|\b(?:الصفحة|القسم|الفصل|الفقرة|الجدول)\s*\d"
            r")",
            q,
        ))

    @staticmethod
    def _check_document_dominance(question: str, *, owner_id: str) -> float:
        """Embed *question* and probe document_chunks for the top score.

        Returns the highest cosine similarity (0.0 if no hits).
        This is a lightweight probe — only 1 result is fetched.
        """
        try:
            embedding_svc = get_embedding_service()
            qdrant = get_qdrant_service()
            qe = embedding_svc.encode_single(question)
            qf = build_user_doc_filter(
                session_id=None, owner_id=owner_id,
                document_id=None, document_ids=None,
            )
            hits = qdrant.search(
                collection=COLLECTION_DOCUMENT_CHUNKS,
                query_vector=qe,
                limit=1,
                score_threshold=0.0,
                query_filter=qf,
            )
            top_score = hits[0]["score"] if hits else 0.0
            logger.debug(
                "Document dominance probe: owner=%s top_score=%.3f",
                owner_id, top_score,
            )
            return top_score
        except Exception:
            logger.warning("Document dominance check failed", exc_info=True)
            return 0.0

    @staticmethod
    def _build_platform_context(results: List[Dict[str, Any]]) -> str:
        """Format platform query results as context for the LLM."""
        if not results:
            return ""

        # Check for my_contributions special structure
        if len(results) == 1 and results[0].get("type") == "my_contributions":
            return ChatLogic._format_my_contributions(results[0])

        parts = []
        for i, r in enumerate(results[:8], 1):
            rtype = r.get("type", "unknown")
            title = r.get("title") or r.get("name", "N/A")
            desc = r.get("description", "")[:200]
            url = r.get("url", "")
            extras = []
            for key in (
                "document_type",
                "field",
                "level",
                "event_type",
                "institution_type",
                "status",
                "language",
                "start_date",
                "end_date",
                "journal",
                "doi",
                "city",
                "country",
                "website",
                "author",
            ):
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
    def _format_my_contributions(data: Dict[str, Any]) -> str:
        """Format the user's own contributions into readable context."""
        category_labels = {
            "tools": "NLP Tools",
            "courses": "Courses",
            "documents": "Documents",
            "corpora": "Corpora",
            "posts": "Posts",
            "questions": "QA Questions",
            "answers": "QA Answers",
            "projects": "Projects",
            "events": "Events",
            "forum_topics": "Forum Topics",
        }
        sections = []
        for key, label in category_labels.items():
            items = data.get(key)
            if not items:
                continue
            lines = [f"📂 {label} ({len(items)}):"]
            for item in items:
                title = item.get("title") or item.get("question") or "Untitled"
                date = item.get("date", "")
                extras = []
                if item.get("type"):
                    extras.append(item["type"])
                if item.get("status"):
                    extras.append(item["status"])
                suffix = f" ({', '.join(extras)})" if extras else ""
                date_str = f" [{date}]" if date else ""
                lines.append(f"  • {title}{suffix}{date_str}")
            sections.append("\n".join(lines))

        if not sections:
            return "You have no contributions on the platform yet."
        return "Here are your contributions on the platform:\n\n" + "\n\n".join(
            sections
        )

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
