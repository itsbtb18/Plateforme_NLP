"""
Session service — PostgreSQL-backed session lifecycle.

Manages chat session CRUD, listing, history retrieval, and auto-titling.
All structured truth lives in PostgreSQL.

Phase 8 — Memory strategy:
  - Uses last N messages within a token budget
  - Optional rolling summary for long-lived sessions
  - Token counting on every persisted message
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func as sqlfunc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import ChatSession, ChatMessage
from app.schemas import SessionInfo, SessionListResponse
from app.config import get_settings
from app.services.memory.tokens import estimate_tokens
from typing import List, Dict, Optional
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
settings = get_settings()


class SessionService:
    """Pure session operations — no RAG, no LLM, no vectors."""

    async def ensure_exists(
        self,
        session_id: str,
        db: AsyncSession,
        user_id: Optional[str] = None,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None,
    ):
        """Ensure a ChatSession row exists for the provided session_id.

        Uses PostgreSQL upsert semantics to avoid race conditions and
        prevent foreign-key failures when persisting messages.
        """
        stmt = (
            pg_insert(ChatSession)
            .values(
                session_id=session_id,
                user_id=user_id,
                user_country=user_country,
                user_city=user_city,
            )
            .on_conflict_do_nothing(index_elements=[ChatSession.session_id])
        )
        await db.execute(stmt)
        await db.commit()

    async def create(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None,
    ) -> str:
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            user_country=user_country,
            user_city=user_city,
        )
        db.add(session)
        await db.commit()
        logger.info("Created session: %s", session_id)
        return session_id

    async def end(self, session_id: str, db: AsyncSession):
        stmt = (
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(is_active=False, last_activity=datetime.utcnow())
        )
        await db.execute(stmt)
        await db.commit()
        logger.info("Ended session: %s", session_id)

    async def delete(self, session_id: str, db: AsyncSession):
        stmt = delete(ChatSession).where(ChatSession.session_id == session_id)
        await db.execute(stmt)
        await db.commit()
        logger.info("Deleted session: %s", session_id)

    async def rename(self, session_id: str, title: str, db: AsyncSession):
        stmt = (
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(title=title)
        )
        await db.execute(stmt)
        await db.commit()

    async def list_sessions(
        self,
        user_id: str,
        db: AsyncSession,
        include_inactive: bool = False,
    ) -> SessionListResponse:
        conditions = [ChatSession.user_id == user_id]
        if not include_inactive:
            conditions.append(ChatSession.is_active == True)  # noqa: E712

        stmt = (
            select(ChatSession)
            .where(*conditions)
            .order_by(ChatSession.last_activity.desc())
        )
        sessions = (await db.execute(stmt)).scalars().all()

        items: List[SessionInfo] = []
        for s in sessions:
            count_result = await db.execute(
                select(sqlfunc.count())
                .select_from(ChatMessage)
                .where(ChatMessage.session_id == s.session_id)
            )
            msg_count = count_result.scalar() or 0

            items.append(SessionInfo(
                session_id=s.session_id,
                title=s.title,
                created_at=s.created_at,
                last_activity=s.last_activity,
                is_active=s.is_active,
                message_count=msg_count,
                preferred_language=s.preferred_language,
            ))

        return SessionListResponse(sessions=items, total=len(items))

    async def get_history(
        self, session_id: str, db: AsyncSession, limit: int = 50,
    ) -> List[Dict]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [
            {
                "role": m.role, "content": m.content, "source": m.source,
                "language": m.language, "created_at": str(m.created_at),
            }
            for m in result.scalars().all()
        ]

    async def auto_title(
        self, session_id: str, first_question: str, db: AsyncSession,
    ):
        """Set session title from the first user message if not already titled."""
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session and not session.title:
            title = first_question.strip()[:60]
            if len(first_question.strip()) > 60:
                title += "..."
            session.title = title
            await db.commit()

    async def update_language(
        self, session_id: str, lang: str, db: AsyncSession,
    ):
        stmt = (
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(preferred_language=lang)
        )
        await db.execute(stmt)
        await db.commit()

    async def get_recent_messages(
        self, session_id: str, db: AsyncSession,
        max_messages: Optional[int] = None,
        token_budget: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Recent messages formatted for LLM chat history.

        Phase 8: returns up to *max_messages* messages (default from config)
        that together fit within *token_budget* tokens.
        """
        limit = max_messages or settings.MAX_HISTORY_MESSAGES
        budget = token_budget or settings.TOKEN_BUDGET_HISTORY

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = [
            m for m in reversed(result.scalars().all())
            if m.role in ("user", "assistant")
        ]

        # Trim from the oldest end until we fit within the token budget
        selected: List[Dict[str, str]] = []
        tokens_used = 0
        for m in reversed(rows):          # newest first
            t = m.token_count or estimate_tokens(m.content)
            if tokens_used + t > budget:
                break
            selected.append({"role": m.role, "content": m.content})
            tokens_used += t

        selected.reverse()                 # back to chronological order
        return selected

    async def get_summary(
        self, session_id: str, db: AsyncSession,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Return the rolling summary, truncated to fit the token budget."""
        result = await db.execute(
            select(ChatSession.summary).where(ChatSession.session_id == session_id)
        )
        summary = result.scalar_one_or_none()
        if not summary:
            return None

        budget = max_tokens or settings.TOKEN_BUDGET_SUMMARY
        if estimate_tokens(summary) > budget:
            chars = budget * 4
            summary = "..." + summary[-chars:]
        return summary

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: Optional[str],
        language: str,
        db: AsyncSession,
        retrieved_count: int = 0,
    ):
        msg = ChatMessage(
            session_id=session_id, role=role, content=content,
            source=source, language=language,
            retrieved_docs_count=retrieved_count,
            token_count=estimate_tokens(content),
        )
        db.add(msg)
        await db.commit()

    # ------------------------------------------------------------------
    # Memory intent helpers (Phase — Memory Intelligence)
    # ------------------------------------------------------------------

    async def get_last_user_query(
        self, session_id: str, db: AsyncSession,
    ) -> Optional[str]:
        """Return the most recent user message content, or None."""
        stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        content = result.scalar_one_or_none()
        if content:
            logger.debug("Memory: last user query found for session %s", session_id)
        else:
            logger.debug("Memory: no prior user query in session %s", session_id)
        return content

    async def get_last_assistant_answer(
        self, session_id: str, db: AsyncSession,
    ) -> Optional[str]:
        """Return the most recent assistant message content, or None."""
        stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "assistant",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        content = result.scalar_one_or_none()
        if content:
            logger.debug("Memory: last assistant answer found for session %s", session_id)
        else:
            logger.debug("Memory: no prior assistant answer in session %s", session_id)
        return content

    async def get_last_two_user_queries(
        self, session_id: str, db: AsyncSession,
    ) -> List[str]:
        """Return the two most recent user messages (chronological order)."""
        stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(2)
        )
        result = await db.execute(stmt)
        rows = [r for r in result.scalars().all()]
        rows.reverse()  # chronological order (oldest first)
        logger.debug(
            "Memory: found %d prior user queries in session %s",
            len(rows), session_id,
        )
        return rows

    async def maybe_trigger_summarisation(self, session_id: str, db: AsyncSession):
        """Fire a Celery task to summarise history if threshold exceeded."""
        count_result = await db.execute(
            select(sqlfunc.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id)
        )
        total = count_result.scalar() or 0
        if total >= settings.HISTORY_SUMMARY_THRESHOLD:
            try:
                from app.tasks.summary_tasks import summarise_chat_history
                summarise_chat_history.delay(session_id)
            except Exception as e:
                logger.warning("Could not enqueue summarisation: %s", e)


# Singleton
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
