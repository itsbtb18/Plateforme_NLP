"""
Faithfulness verification — Phase 6.

Verifies that LLM-generated answers are supported by the retrieved
context.  This is critical for a legal chatbot where hallucinated
legal provisions could have real consequences.

Pipeline integration (in chat_logic.py):
  1. Generate answer via RAG
  2. Verify faithfulness (this module)
  3. If unfaithful → return safe fallback
  4. Persist final answer
"""

import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

_VERIFY_TIMEOUT_SECONDS = 6.0
_VERIFY_MAX_RETRIES = 1
_VERIFY_BASE_DELAY = 0.25

# Intents that skip faithfulness verification (no RAG context)
_SKIP_INTENTS = {
    "general_knowledge",  # No context to verify against
}


async def verify_faithfulness(
    answer: str,
    context: str,
    language: str = "en",
    intent: Optional[str] = None,
) -> bool:
    """Check if the answer is faithful to the retrieved context.

    Returns True if the answer is faithful, False otherwise.
    Skips verification for certain intents (greetings, general knowledge)
    and when there is no context.
    """
    # Skip for intents that don't use RAG
    if intent in _SKIP_INTENTS:
        return True

    # Skip if no context was used
    if not context or not context.strip():
        return True

    # Skip for very short answers (likely simple responses)
    if len(answer.strip()) < 50:
        return True

    try:
        from app.services.llm import get_internal_llm_client
        from app.services.llm.prompts import FAITHFULNESS_PROMPT

        client = get_internal_llm_client()

        # Keep verifier context short to limit latency under load.
        truncated_context = context[:1800] if len(context) > 1800 else context
        truncated_answer = answer[:2000] if len(answer) > 2000 else answer

        prompt = FAITHFULNESS_PROMPT.format(
            context=truncated_context,
            answer=truncated_answer,
        )

        messages = [
            {"role": "system", "content": "You are a factual verification system. Respond with only 'faithful' or 'not_faithful'."},
            {"role": "user", "content": prompt},
        ]

        response = await asyncio.wait_for(
            client.chat_completion(
                messages,
                temperature=0.0,
                max_tokens=10,
                max_retries=_VERIFY_MAX_RETRIES,
                base_delay=_VERIFY_BASE_DELAY,
            ),
            timeout=_VERIFY_TIMEOUT_SECONDS,
        )

        verdict = response.strip().lower().replace('"', '').replace("'", "")

        is_faithful = "faithful" in verdict and "not_faithful" not in verdict

        if not is_faithful:
            logger.warning(
                "Faithfulness check FAILED: verdict='%s' for %s answer (lang=%s)",
                verdict, intent or "unknown", language,
            )
        else:
            logger.debug(
                "Faithfulness check passed: verdict='%s' (intent=%s)",
                verdict, intent,
            )

        return is_faithful

    except Exception as e:
        logger.warning(
            "Faithfulness verification failed (%s), assuming faithful",
            type(e).__name__,
        )
        # On error, assume faithful to avoid blocking the response
        return True


def get_faithfulness_fallback(language: str) -> str:
    """Get the safe fallback message for unfaithful answers."""
    from app.services.llm.prompts import FAITHFULNESS_FALLBACK
    return FAITHFULNESS_FALLBACK.get(language, FAITHFULNESS_FALLBACK["en"])
