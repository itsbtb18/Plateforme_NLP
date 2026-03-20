"""
app.services.llm — LLM client and prompt templates.

Public API:
  - GroqClient, get_groq_client
  - CRITICAL_RULES, SYSTEM_PROMPTS
  - source_rules, rag_prompt
"""
from app.services.llm.client import GroqClient, get_groq_client, get_internal_groq_client
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
    "get_groq_client",
    "get_internal_groq_client",
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
