"""
Gemini API client — LLM inference layer (provider: Google GenAI).

Implements the same public interface as GroqClient so downstream code
can use either provider transparently.  API key is NEVER logged.
"""

from google import genai
from google.genai import types
from app.config import get_settings
from app.services.llm.prompts import (
    CRITICAL_RULES,
    MODE_SYSTEM_PROMPTS,
    SYSTEM_PROMPTS,
    identity_hint,
    rag_prompt,
    source_rules,
)
import asyncio
import logging
import time
import threading
from typing import List, Dict, Optional, Any, AsyncGenerator

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiClient:
    """Client for Google Gemini API — NEVER logs the API key."""

    _REQUEST_TIMEOUT_SECONDS = 30.0  # Gemini can be slightly slower

    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or settings.GENAI_API_KEY
        self.model = model_name or settings.GENAI_MODEL

        if not self.api_key:
            logger.warning("GENAI_API_KEY is not set. Gemini features will fail.")

        self.client = genai.Client(api_key=self.api_key)
        logger.info("Gemini client initialised – model: %s", self.model)

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]):
        """Convert OpenAI-style messages to Gemini format.

        Returns (system_instruction, contents) where:
        - system_instruction is the system message text (or None)
        - contents is a list of Gemini Content objects
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # Gemini uses system_instruction separately
                if system_instruction is None:
                    system_instruction = content
                else:
                    system_instruction += "\n\n" + content
            elif role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=content)],
                    )
                )
            else:  # "user" or anything else
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=content)],
                    )
                )

        return system_instruction, contents

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    _MAX_RETRIES = 2
    _BASE_DELAY = 1.0

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> str:
        """Asynchronous Gemini API call with retry and strict timeout."""
        if not messages:
            raise ValueError("Messages list cannot be empty")

        retries = max_retries if max_retries is not None else self._MAX_RETRIES
        delay_base = base_delay if base_delay is not None else self._BASE_DELAY

        system_instruction, contents = self._convert_messages(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction
        
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                # 8 second harsh timeout on Gemini to prevent 60s hanging
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=8.0
                )
                text = response.text
                if not text:
                    break
                return text
            except Exception as e:
                last_exc = e
                error_str = str(e).lower()
                is_retryable = (
                    "429" in error_str
                    or "rate" in error_str
                    or "503" in error_str
                    or "500" in error_str
                    or "overloaded" in error_str
                )
                if is_retryable and attempt < retries - 1:
                    delay = delay_base * (2 ** attempt)
                    logger.warning(
                        "Gemini retryable error (attempt %d/%d): %s, retrying in %ds",
                        attempt + 1, retries, type(e).__name__, int(delay),
                    )
                    await asyncio.sleep(delay)
                elif isinstance(e, asyncio.TimeoutError):
                    logger.warning("Gemini API call timed out after 8s.")
                    break
                else:
                    break

        logger.error("Gemini API error: %s. Falling back to Groq.", type(last_exc).__name__ if last_exc else "None")
        from app.services.llm.client import get_groq_client
        groq = get_groq_client()
        return await groq.chat_completion(
            messages, temperature, max_tokens, max_retries, base_delay
        )

    # ------------------------------------------------------------------
    # High-level methods
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        *,
        language: str,
        source_type: Optional[str] = None,
        username: Optional[str] = None,
        session_summary: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Build system prompt — same logic as GroqClient."""
        if mode and mode in MODE_SYSTEM_PROMPTS:
            mode_prompts = MODE_SYSTEM_PROMPTS[mode]
            system = mode_prompts.get(language, mode_prompts["en"])
        else:
            system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        if source_type:
            system += source_rules(language, source_type)
        system += identity_hint(username, language)
        if session_summary:
            system += f"\n\n[Previous conversation summary]\n{session_summary}"
        return system

    async def generate_answer_with_context(
        self,
        question: str,
        context: str,
        language: str = "en",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        session_summary: Optional[str] = None,
        source_type: Optional[str] = None,
        username: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """RAG-augmented answer generation."""
        system = self._build_system_prompt(
            language=language,
            source_type=source_type,
            username=username,
            session_summary=session_summary,
            mode=mode,
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        user_msg = rag_prompt(question, context, language, source_type)
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
        """RAG-augmented answer generation — streams tokens."""
        system = self._build_system_prompt(
            language=language,
            source_type=source_type,
            username=username,
            session_summary=session_summary,
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        user_msg = rag_prompt(question, context, language, source_type)
        messages.append({"role": "user", "content": user_msg})

        system_instruction, contents = self._convert_messages(messages)
        config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=settings.GROQ_MAX_TOKENS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        stream = None
        for attempt in range(self._MAX_RETRIES):
            try:
                stream = await asyncio.wait_for(
                    self.client.aio.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=8.0
                )
                break
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = "429" in error_str or "rate" in error_str or "503" in error_str
                if is_retryable and attempt < self._MAX_RETRIES - 1:
                    delay = self._BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Gemini stream rate-limited (attempt %d/%d), retrying in %ds",
                        attempt + 1, self._MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                elif isinstance(e, asyncio.TimeoutError):
                    logger.warning("Gemini initial stream generation timed out after 8s")
                    break
                else:
                    logger.error("Gemini streaming error: %s", type(e).__name__)
                    break

        if stream is None:
            logger.warning("Falling back to Groq stream due to Gemini initial stream failure...")
            from app.services.llm.client import get_groq_client
            fallback_client = get_groq_client()
            async for chunk in fallback_client.generate_answer_with_context_stream(
                question, context, language, chat_history, session_summary, source_type, username
            ):
                yield chunk
            return

        try:
            async for chunk in stream:
                delta = chunk.text or ""
                if delta:
                    yield delta
        except Exception as e:
            logger.error("Gemini aio stream consume error: %s", type(e).__name__)
            logger.warning("Falling back to Groq stream due to Gemini chunk error...")
            from app.services.llm.client import get_groq_client
            fallback_client = get_groq_client()
            async for chunk in fallback_client.generate_answer_with_context_stream(
                question, context, language, chat_history, session_summary, source_type, username
            ):
                yield chunk

    async def quick_answer(
        self, question: str, language: str = "en", username: Optional[str] = None
    ) -> str:
        """Answer without retrieved context."""
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])

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

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        return await self.chat_completion(messages, max_tokens=settings.GROQ_MAX_TOKENS)

    async def quick_answer_stream(
        self, question: str, language: str = "en", username: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Answer without context — streams tokens."""
        system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])
        system += CRITICAL_RULES.get(language, CRITICAL_RULES["en"])
        guardrails = {
            "ar": "\n\nأنت الآن في وضع المحادثة. استخدم معرفتك ومنطقك للإجابة بشكل طبيعي. إذا لم تكن واثقاً من الإجابة، قل ذلك بصراحة. لا تروّج للمنصة تلقائياً.",
            "fr": "\n\nVous êtes en mode conversationnel. Utilisez vos connaissances et votre raisonnement pour répondre naturellement. Si vous n'êtes pas sûr, dites-le clairement. Ne faites pas la promotion de la plateforme spontanément.",
            "en": "\n\nYou are in conversational mode. Use your knowledge and reasoning to answer naturally. If you are unsure, say so clearly. Do not promote the platform spontaneously.",
        }
        system += guardrails.get(language, guardrails["en"])
        system += identity_hint(username, language)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        system_instruction, contents = self._convert_messages(messages)
        config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=settings.GROQ_MAX_TOKENS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        stream = None
        for attempt in range(self._MAX_RETRIES):
            try:
                stream = await asyncio.wait_for(
                    self.client.aio.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=8.0
                )
                break
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = "429" in error_str or "rate" in error_str or "503" in error_str
                if is_retryable and attempt < self._MAX_RETRIES - 1:
                    delay = self._BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Gemini quick stream rate-limited (attempt %d/%d), retrying in %ds",
                        attempt + 1, self._MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                elif isinstance(e, asyncio.TimeoutError):
                    logger.warning("Gemini initial quick stream timed out after 8s")
                    break
                else:
                    logger.error("Gemini quick_answer stream error: %s", type(e).__name__)
                    break

        if stream is None:
            logger.warning("Falling back to Groq stream due to Gemini initial quick stream failure...")
            from app.services.llm.client import get_groq_client
            fallback_client = get_groq_client()
            async for chunk in fallback_client.quick_answer_stream(question, language, username):
                yield chunk
            return

        try:
            async for chunk in stream:
                delta = chunk.text or ""
                if delta:
                    yield delta
        except Exception as e:
            logger.error("Gemini aio stream consume error: %s", type(e).__name__)
            logger.warning("Falling back to Groq stream due to Gemini quick chunk error...")
            from app.services.llm.client import get_groq_client
            fallback_client = get_groq_client()
            async for chunk in fallback_client.quick_answer_stream(question, language, username):
                yield chunk

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
