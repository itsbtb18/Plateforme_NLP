"""
Chat history summarisation tasks.
"""
import logging
from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="app.tasks.summarise_chat_history", max_retries=1)
def summarise_chat_history(self, session_id: str):
    """Summarise older chat messages into a rolling summary."""
    import asyncio
    asyncio.run(_summarise_chat_async(session_id))


async def _summarise_chat_async(session_id: str):
    from app.db import AsyncSessionLocal
    from app.models import ChatSession, ChatMessage
    from app.services.llm.client import get_llm_client
    from sqlalchemy import select, delete
    from app.config import get_settings

    settings = get_settings()
    llm = get_llm_client()

    async with AsyncSessionLocal() as db:
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await db.execute(msg_stmt)
        messages = result.scalars().all()

        if len(messages) < settings.HISTORY_SUMMARY_THRESHOLD:
            return

        keep_recent = 6
        to_summarise = messages[:-keep_recent] if len(messages) > keep_recent else []
        if not to_summarise:
            return

        conversation_text = "\n".join(
            f"{m.role}: {m.content[:500]}" for m in to_summarise
        )

        # Detect dominant language
        lang_counts: dict[str, int] = {}
        for m in to_summarise:
            lang = m.language or "en"
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        session_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "en"

        _SUMMARY_PROMPTS = {
            "ar": (
                "لخّص المحادثة التالية بإيجاز مع الحفاظ على الحقائق الأساسية "
                "وتفضيلات المستخدم والقرارات المتخذة. اكتب الملخص فقط باللغة العربية:\n\n"
            ),
            "fr": (
                "Résumez la conversation suivante de manière concise en préservant "
                "les faits clés, les préférences et les décisions. "
                "Rédigez uniquement le résumé en français :\n\n"
            ),
            "en": (
                "Summarise the following conversation concisely, preserving key facts, "
                "user preferences, and any decisions made. Output only the summary:\n\n"
            ),
        }
        prompt = _SUMMARY_PROMPTS.get(session_lang, _SUMMARY_PROMPTS["en"])
        summary = await llm.quick_answer(prompt + conversation_text, session_lang)

        sess_stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        sess_result = await db.execute(sess_stmt)
        session = sess_result.scalar_one_or_none()
        if session:
            existing = session.summary or ""
            session.summary = (existing + "\n\n" + summary).strip()[-4000:]

        ids_to_delete = [m.id for m in to_summarise]
        await db.execute(
            delete(ChatMessage).where(ChatMessage.id.in_(ids_to_delete))
        )
        await db.commit()
        logger.info("Summarised %d messages for session %s", len(to_summarise), session_id)


@celery.task(bind=True, name="app.tasks.summarise_text", max_retries=1)
def summarise_text(self, text: str, language: str = "en") -> str:
    """Summarise arbitrary long text via Groq."""
    import asyncio
    return asyncio.run(_summarise_text_async(text, language))


async def _summarise_text_async(text: str, language: str) -> str:
    from app.services.llm.client import get_llm_client

    prompt = (
        "Summarise the following text concisely, preserving key facts. "
        f"Respond in {'Arabic' if language == 'ar' else 'French' if language == 'fr' else 'English'}.\n\n"
        f"{text[:12000]}"
    )
    return await get_llm_client().quick_answer(prompt, language)
