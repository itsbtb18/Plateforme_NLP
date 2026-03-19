"""
Groq API client — LLM inference layer.

Handles chat completion, RAG-augmented generation, and quick answers.
API key is NEVER logged.
"""

from groq import Groq, RateLimitError
from groq.types.chat import ChatCompletionMessageParam, ChatCompletion
from app.config import get_settings
from app.services.llm.prompts import (
    CRITICAL_RULES,
    SYSTEM_PROMPTS,
    identity_hint,
    rag_prompt,
    source_rules,
)
import asyncio
import logging
import time
from typing import List, Dict, Optional, Any, AsyncGenerator
import threading

logger = logging.getLogger(__name__)
settings = get_settings()


class GroqClient:
    """Client for Groq API interactions — NEVER logs the API key."""

    def __init__(self):
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY not configured")
        self.client = Groq(api_key=api_key, timeout=60.0)
        self.model = settings.GROQ_MODEL
        logger.info("Groq client initialised – model: %s", self.model)

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    _MAX_RETRIES = 3
    _BASE_DELAY = 2  # seconds

    def _sync_chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Synchronous Groq API call with retry on rate-limit.

        Retries up to _MAX_RETRIES times with exponential backoff when
        the Groq API returns 429 Too Many Requests.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        last_exc: Optional[Exception] = None
        for attempt in range(self._MAX_RETRIES):
            try:
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
            except RateLimitError as e:
                last_exc = e
                delay = self._BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq rate-limited (attempt %d/%d), retrying in %ds",
                    attempt + 1, self._MAX_RETRIES, delay,
                )
                time.sleep(delay)

        # All retries exhausted — re-raise so chat_completion returns fallback
        raise last_exc  # type: ignore[misc]

    async def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        try:
            return await asyncio.to_thread(
                self._sync_chat_completion,
                messages,
                temperature,
                max_tokens,
            )
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
        username: Optional[str] = None,
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
        system += identity_hint(username, language)

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

    async def generate_answer_with_context_stream(
        self,
        question: str,
        context: str,
        language: str = "en",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        session_summary: Optional[str] = None,
        source_type: Optional[str] = None,
        username: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """RAG-augmented answer generation — streams tokens as they arrive."""
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        if source_type:
            system += source_rules(language, source_type)
        system += identity_hint(username, language)

        if session_summary:
            system += f"\n\n[Previous conversation summary]\n{session_summary}"

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        user_msg = rag_prompt(question, context, language)
        messages.append({"role": "user", "content": user_msg})

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=settings.GROQ_MAX_TOKENS,
                stream=True,
            )
        except Exception as e:
            logger.error("Groq streaming error: %s", type(e).__name__)
            yield self._fallback_message("en")
            return

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def consume():
            try:
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    content = (delta.content or "") if delta else ""
                    if content:
                        asyncio.run_coroutine_threadsafe(queue.put(content), loop)
            except Exception as e:
                logger.error("Groq stream consume error: %s", e)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        thread = threading.Thread(target=consume)
        thread.start()

        while True:
            content = await queue.get()
            if content is None:
                break
            yield content

    async def quick_answer(self, question: str, language: str = "en", username: Optional[str] = None) -> str:
        """Answer without retrieved context.

        Phase 10 — Safety: critical rules are included even without RAG.
        Phase 13 — Anti-hallucination: domain-scoped guardrail.
        The LLM is reminded it has no retrieved documents and must stay
        within its domain expertise (Arabic NLP) or admit uncertainty.
        """
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])

        # Phase 9 — Conversational Mode guardrail (no RAG context)
        guardrails = {
            "ar": (
                "\n\nأنت الآن في وضع المحادثة. استخدم معرفتك ومنطقك للإجابة بشكل طبيعي. "
                "إذا لم تكن واثقاً من الإجابة، قل ذلك بصراحة. "
                "لا تروّج للمنصة تلقائياً."
            ),
            "fr": (
                "\n\nVous êtes en mode conversationnel. Utilisez vos connaissances et votre raisonnement pour répondre naturellement. "
                "Si vous n'êtes pas sûr, dites-le clairement. "
                "Ne faites pas la promotion de la plateforme spontanément."
            ),
            "en": (
                "\n\nYou are in conversational mode. Use your knowledge and reasoning to answer naturally. "
                "If you are unsure, say so clearly. "
                "Do not promote the platform spontaneously."
            ),
        }
        system += guardrails.get(language, guardrails["en"])
        system += identity_hint(username, language)

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        return await self.chat_completion(messages, max_tokens=settings.GROQ_MAX_TOKENS)

    async def quick_answer_stream(
        self, question: str, language: str = "en", username: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Answer without context — streams tokens as they arrive."""
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        guardrails = {
            "ar": "\n\nأنت الآن في وضع المحادثة. استخدم معرفتك ومنطقك للإجابة بشكل طبيعي. إذا لم تكن واثقاً من الإجابة، قل ذلك بصراحة. لا تروّج للمنصة تلقائياً.",
            "fr": "\n\nVous êtes en mode conversationnel. Utilisez vos connaissances et votre raisonnement pour répondre naturellement. Si vous n'êtes pas sûr, dites-le clairement. Ne faites pas la promotion de la plateforme spontanément.",
            "en": "\n\nYou are in conversational mode. Use your knowledge and reasoning to answer naturally. If you are unsure, say so clearly. Do not promote the platform spontaneously.",
        }
        system += guardrails.get(language, guardrails["en"])
        system += identity_hint(username, language)

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=settings.GROQ_MAX_TOKENS,
                stream=True,
            )
        except Exception as e:
            logger.error("Groq quick_answer stream error: %s", type(e).__name__)
            yield self._fallback_message(language)
            return

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def consume():
            try:
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    content = (delta.content or "") if delta else ""
                    if content:
                        asyncio.run_coroutine_threadsafe(queue.put(content), loop)
            except Exception as e:
                logger.error("Groq stream consume error: %s", e)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        thread = threading.Thread(target=consume)
        thread.start()

        while True:
            content = await queue.get()
            if content is None:
                break
            yield content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_message(language: str) -> str:
        msgs = {
            "ar": "أعتذر، لم أتمكن من إكمال الإجابة الآن. يرجى إعادة صياغة سؤالك أو المحاولة بعد لحظات.",
            "fr": "Je n'ai pas pu compléter la réponse pour le moment. Veuillez reformuler votre question ou réessayer dans un instant.",
            "en": "I wasn't able to complete my answer right now. Please rephrase your question or try again in a moment.",
        }
        return msgs.get(language, msgs["en"])

    @staticmethod
    def is_fallback(text: str) -> bool:
        """Return True if *text* is one of the fallback messages."""
        _markers = {
            "لم أتمكن من إكمال",
            "pas pu compl\u00e9ter la r\u00e9ponse",
            "wasn't able to complete",
        }
        return any(m in text for m in _markers)


# Singleton
_groq_client = None


def get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
