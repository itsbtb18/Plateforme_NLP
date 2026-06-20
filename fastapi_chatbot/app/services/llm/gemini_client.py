"""Gemini client compatibility module.

This module re-exports GeminiClient from app.services.llm.client so
imports like `from app.services.llm.gemini_client import GeminiClient`
continue to work after merge/rebase operations.
"""

from app.services.llm.client import GeminiClient

__all__ = ["GeminiClient"]
