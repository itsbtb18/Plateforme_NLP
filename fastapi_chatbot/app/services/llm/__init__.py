"""
app.services.llm — LLM client and prompt templates.

Public API:
    - GroqClient, get_groq_client, get_internal_groq_client  (backward compat)
    - GeminiClient                                           (Gemini provider)
    - LLMClient, get_llm_client, get_internal_llm_client     (provider-aware)
  - get_llm_client, get_internal_llm_client
  - CRITICAL_RULES, SYSTEM_PROMPTS
  - source_rules, rag_prompt
"""
from app.services.llm.client import (
    GroqClient,
        LLMClient,
    get_groq_client,
    get_internal_groq_client,
    get_llm_client,
    get_internal_llm_client,
)
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.prompts import (
    CRITICAL_RULES,
    SYSTEM_PROMPTS,
    CLASSIFICATION_PROMPT,
    QUERY_REWRITE_PROMPT,
    FAITHFULNESS_PROMPT,
    FAITHFULNESS_FALLBACK,
    VALID_INTENTS,
    source_rules,
    rag_prompt,
)

__all__ = [
    "GroqClient",
    "GeminiClient",
    "LLMClient",
    "get_groq_client",
    "get_internal_groq_client",
    "get_llm_client",
    "get_internal_llm_client",
    "CRITICAL_RULES",
    "SYSTEM_PROMPTS",
    "CLASSIFICATION_PROMPT",
    "QUERY_REWRITE_PROMPT",
    "FAITHFULNESS_PROMPT",
    "FAITHFULNESS_FALLBACK",
    "VALID_INTENTS",
    "source_rules",
    "rag_prompt",
]
