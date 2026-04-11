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
    MODE_SYSTEM_PROMPTS,
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

    # Keep provider calls fail-fast to avoid minute-long waits under 429/load.
    _REQUEST_TIMEOUT_SECONDS = 8.0

    def __init__(self, api_key: str = None, model_name: str = None):
        """Initialise the client with a specific key and model.
        
        Defaults to settings.GROQ_API_KEY / settings.GROQ_MODEL if not provided.
        """
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model_name or settings.GROQ_MODEL
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. LLM features will fail.")

        self.client = Groq(
            api_key=self.api_key,
            timeout=self._REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        logger.info("Groq client initialised – model: %s", self.model)

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    _MAX_RETRIES = 1
    _BASE_DELAY = 0.5  # seconds

    def _get_alt_client_and_model(self):
        """Return an alternate Groq client/model when internal credentials differ.

        This is used as a final failover path when the primary key/model is
        rate-limited.
        """
        alt_key = settings.GROQ_INTERNAL_API_KEY
        if not alt_key or alt_key == self.api_key:
            return None, None
        alt_model = settings.GROQ_INTERNAL_MODEL or self.model
        return (
            Groq(
                api_key=alt_key,
                timeout=self._REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            ),
            alt_model,
        )

    def _build_system_prompt(
        self,
        *,
        language: str,
        source_type: Optional[str] = None,
        username: Optional[str] = None,
        session_summary: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Build system prompt with explicit precedence.

        Precedence is intentional:
          1) Base system role (or mode-specific role if mode is set)
          2) General critical rules
          3) Source-specific rules (legal/platform/user_document)
             appended LAST so they override general style constraints.
          4) Identity hint
          5) Session summary
        """
        # Phase 6: Use mode-specific prompt if available
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

    def _sync_chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> str:
        """Synchronous Groq API call with retry on rate-limit.

        Retries up to _MAX_RETRIES times with exponential backoff when
        the Groq API returns 429 Too Many Requests.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        retries = max_retries if max_retries is not None else self._MAX_RETRIES
        delay_base = base_delay if base_delay is not None else self._BASE_DELAY

        last_exc: Optional[Exception] = None
        for attempt in range(retries):
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
                delay = delay_base * (2 ** attempt)
                logger.warning(
                    "Groq rate-limited (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    retries,
                    int(delay) if delay >= 1 else delay,
                )
                time.sleep(delay)

        # Final failover: try alternate internal key/model once.
        alt_client, alt_model = self._get_alt_client_and_model()
        if alt_client and alt_model:
            try:
                logger.warning(
                    "Primary Groq key/model exhausted; trying alternate model %s",
                    alt_model,
                )
                response = alt_client.chat.completions.create(
                    model=alt_model,
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
                logger.error("Alternate Groq completion failed: %s", type(e).__name__)

        # All retries exhausted — re-raise so chat_completion returns fallback
        raise last_exc  # type: ignore[misc]

    async def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
    ) -> str:
        try:
            return await asyncio.to_thread(
                self._sync_chat_completion,
                messages,
                temperature,
                max_tokens,
                max_retries,
                base_delay,
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
        mode: Optional[str] = None,
    ) -> str:
        """RAG-augmented answer generation.

        Phase 9 — Prompt structure (strict order):
          1. System instructions  (role + critical rules)
          2. Conversation memory   (summary + recent messages)
          3. Retrieved context     (labelled by source type)
          4. User query
        """
        # 1) SYSTEM INSTRUCTIONS + 2) CONVERSATION MEMORY
        system = self._build_system_prompt(
            language=language,
            source_type=source_type,
            username=username,
            session_summary=session_summary,
            mode=mode,
        )

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        # 3) RETRIEVED CONTEXT + 4) USER QUERY
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
        """RAG-augmented answer generation — streams tokens as they arrive."""
        system = self._build_system_prompt(
            language=language,
            source_type=source_type,
            username=username,
            session_summary=session_summary,
        )

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]
        if chat_history:
            messages.extend(chat_history)

        user_msg = rag_prompt(question, context, language, source_type)
        messages.append({"role": "user", "content": user_msg})

        stream = None
        for attempt in range(self._MAX_RETRIES):
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=settings.GROQ_MAX_TOKENS,
                    stream=True,
                )
                break
            except RateLimitError:
                delay = self._BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq stream rate-limited (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    self._MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error("Groq streaming error: %s", type(e).__name__)
                break

        if stream is None:
            alt_client, alt_model = self._get_alt_client_and_model()
            if alt_client and alt_model:
                try:
                    logger.warning(
                        "Primary Groq stream exhausted; trying alternate model %s",
                        alt_model,
                    )
                    stream = alt_client.chat.completions.create(
                        model=alt_model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=settings.GROQ_MAX_TOKENS,
                        stream=True,
                    )
                except Exception as e:
                    logger.error("Alternate Groq streaming error: %s", type(e).__name__)

        if stream is None:
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

        stream = None
        for attempt in range(self._MAX_RETRIES):
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=settings.GROQ_MAX_TOKENS,
                    stream=True,
                )
                break
            except RateLimitError:
                delay = self._BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq quick stream rate-limited (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    self._MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error("Groq quick_answer stream error: %s", type(e).__name__)
                break

        if stream is None:
            alt_client, alt_model = self._get_alt_client_and_model()
            if alt_client and alt_model:
                try:
                    logger.warning(
                        "Primary Groq quick stream exhausted; trying alternate model %s",
                        alt_model,
                    )
                    stream = alt_client.chat.completions.create(
                        model=alt_model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=settings.GROQ_MAX_TOKENS,
                        stream=True,
                    )
                except Exception as e:
                    logger.error(
                        "Alternate Groq quick stream error: %s",
                        type(e).__name__,
                    )

        if stream is None:
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


# ---------------------------------------------------------------------------
# Type alias for provider-agnostic usage
# ---------------------------------------------------------------------------
from typing import Union

# Import here to allow type usage; actual instantiation is deferred.
from app.services.llm.gemini_client import GeminiClient

LLMClient = Union[GroqClient, GeminiClient]

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
_groq_client = None
_internal_groq_client = None
_gemini_client = None
_internal_gemini_client = None


def get_groq_client() -> GroqClient:
    """Get the primary (user-facing chatbot) Groq client.

    Kept for backward compatibility — always returns GroqClient.
    """
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client


def get_internal_groq_client() -> GroqClient:
    """Get the internal Groq client (for classification, rewriting, etc.).

    Kept for backward compatibility — always returns GroqClient.
    """
    global _internal_groq_client
    if _internal_groq_client is None:
        key = settings.GROQ_INTERNAL_API_KEY or settings.GROQ_API_KEY
        model = settings.GROQ_INTERNAL_MODEL or settings.GROQ_MODEL
        _internal_groq_client = GroqClient(api_key=key, model_name=model)
    return _internal_groq_client


def _get_gemini_client() -> GeminiClient:
    """Singleton for user-facing Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def _get_internal_gemini_client() -> GeminiClient:
    """Singleton for internal Gemini client."""
    global _internal_gemini_client
    if _internal_gemini_client is None:
        key = settings.GENAI_INTERNAL_API_KEY or settings.GENAI_API_KEY
        model = settings.GENAI_INTERNAL_MODEL or settings.GENAI_MODEL
        _internal_gemini_client = GeminiClient(api_key=key, model_name=model)
    return _internal_gemini_client


def get_llm_client() -> LLMClient:
    """Provider-aware: returns GeminiClient or GroqClient based on LLM_PROVIDER_CHAT."""
    provider = settings.LLM_PROVIDER_CHAT.strip().lower()
    if provider == "gemini":
        return _get_gemini_client()
    return get_groq_client()


def get_internal_llm_client() -> LLMClient:
    """Provider-aware: returns GeminiClient or GroqClient based on LLM_PROVIDER_INTERNAL."""
    provider = settings.LLM_PROVIDER_INTERNAL.strip().lower()
    if provider == "gemini":
        return _get_internal_gemini_client()
    return get_internal_groq_client()

