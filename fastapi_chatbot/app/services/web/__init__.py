"""Web search services — Exa (RAG fallback) + Tavily (user-triggered web mode)."""

from app.services.web.exa_client import search_exa
from app.services.web.tavily_client import search_tavily
from app.services.web.confidence import compute_retrieval_confidence
from app.services.web.policy import ExaBudgetPolicy

__all__ = [
    "search_exa",
    "search_tavily",
    "compute_retrieval_confidence",
    "ExaBudgetPolicy",
]
