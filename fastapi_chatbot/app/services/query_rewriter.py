"""
Query rewriter — Phase 5.

Rewrites follow-up questions in multi-turn conversations into
standalone queries that carry all necessary context.  This improves
retrieval accuracy for conversational follow-ups like:

  Turn 1: "What are the graduation procedures?"
  Turn 2: "And the deadlines?"  →  "What are the deadlines for graduation procedures?"

The rewriter uses a lightweight LLM call with the QUERY_REWRITE_PROMPT.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Short queries with pronouns / references are likely follow-ups
_MIN_STANDALONE_WORDS = 6


def _needs_rewrite(question: str, history: List[Dict[str, Any]]) -> bool:
    """Heuristic: does this question need rewriting?

    Returns True if:
    - There is conversation history, AND
    - The question is short (< 6 words), OR
    - The question starts with a conjunction/pronoun/reference word
    """
    if not history:
        return False

    words = question.strip().split()
    if len(words) < _MIN_STANDALONE_WORDS:
        return True

    # Reference words that suggest a follow-up (multilingual)
    _follow_up_starts = {
        # English
        "and", "but", "also", "what", "how", "why", "when", "where",
        "is", "are", "does", "do", "can", "could", "would",
        "it", "its", "this", "that", "these", "those",
        "the", "their", "them",
        # French
        "et", "mais", "aussi", "quel", "quelle", "quels", "quelles",
        "comment", "pourquoi", "quand", "où", "est-ce",
        "il", "elle", "ce", "cette", "ces", "leur", "leurs",
        # Arabic
        "و", "لكن", "أيضا", "ما", "كيف", "لماذا", "متى", "أين",
        "هل", "هذا", "هذه", "ذلك", "تلك",
    }

    first_word = words[0].lower().rstrip("?!.,")
    return first_word in _follow_up_starts


def _format_history(history: List[Dict[str, Any]], max_turns: int = 4) -> str:
    """Format recent conversation history for the rewrite prompt."""
    recent = history[-max_turns * 2:]  # last N turns (user + assistant)
    lines = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # Truncate long messages
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def rewrite_query(
    question: str,
    history: List[Dict[str, Any]],
    language: str = "en",
) -> str:
    """Rewrite a follow-up question into a standalone query.

    Returns the original question if no rewrite is needed or if rewriting fails.
    """
    if not _needs_rewrite(question, history):
        return question

    try:
        from app.services.llm import get_internal_llm_client
        from app.services.llm.prompts import QUERY_REWRITE_PROMPT

        client = get_internal_llm_client()
        formatted_history = _format_history(history)
        
        # Phase 8.1: Explicit language-lock in rewriter
        lang_note = ""
        if language == "ar":
            lang_note = "\n(Strict rule: The rewritten question MUST be in ARABIC.)"
        elif language == "fr":
            lang_note = "\n(Règle stricte: La question reformulée DOIT être en FRANÇAIS.)"
            
        prompt = QUERY_REWRITE_PROMPT.format(
            history=formatted_history,
            question=question,
        )
        if lang_note:
            prompt += lang_note

        messages = [
            {"role": "system", "content": f"You are a query rewriter. Respond only with the rewritten question in {language}."},
            {"role": "user", "content": prompt},
        ]

        rewritten = await client.chat_completion(
            messages, temperature=0.0, max_tokens=250,
        )
        rewritten = rewritten.strip().strip('"').strip("'")

        # Sanity check: rewritten should not be empty or much longer
        if not rewritten or len(rewritten) > len(question) * 5:
            logger.debug("Rewrite rejected (length check): returning original")
            return question

        # Check for fallback/error response from client
        _FALLBACK_PHRASES = {
            "عذراً",         # Arabic fallback start
            "Désolé",        # French fallback start
            "Sorry, an error",  # English fallback start
        }
        if any(rewritten.startswith(p) for p in _FALLBACK_PHRASES):
            return question

        logger.info(
            "Query rewritten: '%s' → '%s'",
            question[:50], rewritten[:50],
        )
        return rewritten

    except Exception as e:
        logger.warning("Query rewriting failed (%s), using original", type(e).__name__)
        return question
