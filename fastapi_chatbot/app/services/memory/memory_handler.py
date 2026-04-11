"""
Memory intent handler — Phase: Memory Intelligence.

Orchestrates memory-aware operations (translate, repeat, summarise,
compare prior turns) without triggering full RAG retrieval.

Called from chat_logic.py when a memory_* intent is classified.
"""

import logging
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory import get_session_service

logger = logging.getLogger(__name__)

# ── Target-language extraction ────────────────────────────────────────

_LANG_PATTERNS = {
    "en": re.compile(
        r"\b(?:to\s+)?(?:english|anglais|الإنجليزية|انجليزي)\b",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"\b(?:to\s+|en\s+)?(?:french|français|فرنسي|الفرنسية)\b",
        re.IGNORECASE,
    ),
    "ar": re.compile(
        r"\b(?:to\s+|إلى\s+)?(?:arabic|arabe|عربي|العربية)\b",
        re.IGNORECASE,
    ),
}


def extract_target_language(question: str) -> str:
    """Detect target language from user command. Defaults to 'en'."""
    for lang, pattern in _LANG_PATTERNS.items():
        if pattern.search(question):
            return lang
    return "en"  # default


# ── Translation via internal LLM ──────────────────────────────────────

async def translate_text(text: str, target_lang: str) -> str:
    """Translate text using the internal Groq LLM (literal-preserving)."""
    lang_names = {"en": "English", "fr": "French", "ar": "Arabic"}
    target_name = lang_names.get(target_lang, "English")

    try:
        from app.services.llm import get_internal_llm_client

        client = get_internal_llm_client()
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a precise translator. Translate the following text to {target_name}. "
                    "Preserve the meaning exactly. For legal/technical terms, keep them literal. "
                    "Return ONLY the translation, nothing else."
                ),
            },
            {"role": "user", "content": text},
        ]
        result = await client.chat_completion(
            messages, temperature=0.1, max_tokens=500,
        )
        return result.strip()
    except Exception as e:
        logger.warning("Translation failed (%s), returning original", type(e).__name__)
        return text


# ── Graceful no-history messages ──────────────────────────────────────

_NO_HISTORY_MSG = {
    "ar": "لا توجد رسائل سابقة في هذه المحادثة.",
    "fr": "Il n'y a pas de messages précédents dans cette conversation.",
    "en": "There are no previous messages in this conversation.",
}

_NO_TWO_QUERIES_MSG = {
    "ar": "لا توجد رسالتان سابقتان للمقارنة في هذه المحادثة.",
    "fr": "Il n'y a pas deux questions précédentes à comparer dans cette conversation.",
    "en": "There are not enough previous questions to compare in this conversation.",
}


def _no_history(language: str) -> str:
    return _NO_HISTORY_MSG.get(language, _NO_HISTORY_MSG["en"])


def _no_two_queries(language: str) -> str:
    return _NO_TWO_QUERIES_MSG.get(language, _NO_TWO_QUERIES_MSG["en"])


# ── Main handler ──────────────────────────────────────────────────────

async def handle_memory_intent(
    intent: str,
    session_id: str,
    question: str,
    language: str,
    db: AsyncSession,
) -> str:
    """Dispatch a memory intent and return the answer string.

    Returns a user-facing answer without running full RAG retrieval.
    """
    sessions = get_session_service()

    if intent == "memory_translate_last_user_query":
        last_query = await sessions.get_last_user_query(session_id, db)
        if not last_query:
            logger.info("memory_action=translate memory_hit=miss session=%s", session_id)
            return _no_history(language)

        target_lang = extract_target_language(question)
        translated = await translate_text(last_query, target_lang)
        logger.info(
            "memory_action=translate memory_hit=hit target_lang=%s session=%s",
            target_lang, session_id,
        )
        return translated
    elif intent == "memory_translate_last_answer":
        last_answer = await sessions.get_last_assistant_answer(session_id, db)
        if not last_answer:
            logger.info("memory_action=translate_last_answer memory_hit=miss session=%s", session_id)
            return _no_history(language)

        target_lang = extract_target_language(question)
        translated = await translate_text(last_answer, target_lang)
        logger.info(
            "memory_action=translate_last_answer memory_hit=hit target_lang=%s session=%s",
            target_lang, session_id,
        )
        return translated

    elif intent == "memory_repeat_last_user_query":
        last_query = await sessions.get_last_user_query(session_id, db)
        if not last_query:
            logger.info("memory_action=repeat memory_hit=miss session=%s", session_id)
            return _no_history(language)

        logger.info("memory_action=repeat memory_hit=hit session=%s", session_id)
        return last_query

    elif intent == "memory_summarize_last_answer":
        last_answer = await sessions.get_last_assistant_answer(session_id, db)
        if not last_answer:
            logger.info("memory_action=summarize memory_hit=miss session=%s", session_id)
            return _no_history(language)

        # Use LLM to summarise
        try:
            from app.services.llm import get_internal_llm_client

            client = get_internal_llm_client()
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"Summarise the following text concisely in {language}. "
                        "Keep the key facts. Return ONLY the summary."
                    ),
                },
                {"role": "user", "content": last_answer[:2000]},
            ]
            summary = await client.chat_completion(
                messages, temperature=0.3, max_tokens=300,
            )
            logger.info("memory_action=summarize memory_hit=hit session=%s", session_id)
            return summary.strip()
        except Exception as e:
            logger.warning("Summarize failed (%s), returning truncated answer", type(e).__name__)
            return last_answer[:500] + ("..." if len(last_answer) > 500 else "")

    elif intent == "memory_compare_last_two_queries":
        queries = await sessions.get_last_two_user_queries(session_id, db)
        if len(queries) < 2:
            logger.info("memory_action=compare memory_hit=miss session=%s", session_id)
            return _no_two_queries(language)

        try:
            from app.services.llm import get_internal_llm_client

            client = get_internal_llm_client()
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"Compare the following two user queries and explain their similarities "
                        f"and differences. Respond in {language}. Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Query 1: {queries[0]}\n\nQuery 2: {queries[1]}",
                },
            ]
            comparison = await client.chat_completion(
                messages, temperature=0.3, max_tokens=400,
            )
            logger.info("memory_action=compare memory_hit=hit session=%s", session_id)
            return comparison.strip()
        except Exception as e:
            logger.warning("Compare failed (%s)", type(e).__name__)
            return f"Query 1: {queries[0]}\n\nQuery 2: {queries[1]}"

    else:
        logger.warning("Unknown memory intent: %s", intent)
        return _no_history(language)
