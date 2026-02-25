"""
Groq API client — LLM inference layer.

Handles chat completion, RAG-augmented generation, and quick answers.
API key is NEVER logged.
"""
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam, ChatCompletion
from app.config import get_settings
from app.services.llm.prompts import (
    CRITICAL_RULES,
    SYSTEM_PROMPTS,
    source_rules,
    rag_prompt,
)
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)
settings = get_settings()


class GroqClient:
    """Client for Groq API interactions — NEVER logs the API key."""

    def __init__(self):
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY not configured")
        self.client = Groq(api_key=api_key)
        self.model = settings.GROQ_MODEL
        logger.info("Groq client initialised – model: %s", self.model)

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    async def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        try:
            if not messages:
                raise ValueError("Messages list cannot be empty")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            if not isinstance(response, ChatCompletion):
                raise ValueError("Unexpected response type from Groq API")
            content = response.choices[0].message.content
            if not content:
                return self._fallback_message("en")
            return content
        except Exception as e:
            logger.error("Groq API error: %s", type(e).__name__)
            fb_lang = "en"
            for m in reversed(messages):
                if m.get("role") == "system":
                    text = m.get("content", "")
                    if "العربية" in text or "عربية" in text:
                        fb_lang = "ar"
                    elif "français" in text.lower():
                        fb_lang = "fr"
                    break
            return self._fallback_message(fb_lang)

    # ------------------------------------------------------------------
    # High-level methods
    # ------------------------------------------------------------------

    async def generate_answer_with_context(
        self,
        question: str,
        context: str,
        language: str = "en",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        session_summary: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> str:
        """RAG-augmented answer generation.

        Phase 9 — Prompt structure (strict order):
          1. System instructions  (role + critical rules)
          2. Conversation memory   (summary + recent messages)
          3. Retrieved context     (labelled by source type)
          4. User query
        """
        # 1) SYSTEM INSTRUCTIONS
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        if source_type:
            system += source_rules(language, source_type)

        # 2) CONVERSATION MEMORY
        if session_summary:
            system += f"\n\n[Previous conversation summary]\n{session_summary}"

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        # 3) RETRIEVED CONTEXT + 4) USER QUERY
        user_msg = rag_prompt(question, context, language)
        messages.append({"role": "user", "content": user_msg})

        return await self.chat_completion(messages, max_tokens=settings.GROQ_MAX_TOKENS)

    async def quick_answer(self, question: str, language: str = "en") -> str:
        """Answer without retrieved context.

        Phase 10 — Safety: critical rules are included even without RAG.
        """
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        # Use configured max_tokens (capped at 2048 for non-RAG answers)
        tokens = min(settings.GROQ_MAX_TOKENS, 2048)
        return await self.chat_completion(messages, max_tokens=tokens)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_message(language: str) -> str:
        msgs = {
            "ar": "عذراً، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.",
            "fr": "Désolé, une erreur s'est produite. Veuillez réessayer.",
            "en": "Sorry, an error occurred while processing your request. Please try again.",
        }
        return msgs.get(language, msgs["en"])


# Singleton
_groq_client = None


def get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
