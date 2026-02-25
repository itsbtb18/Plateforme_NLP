"""
Heuristic-based intent classifier for routing queries.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List

from app.services.language import get_language_service
from app.services.classifier.patterns import (
    METADATA_PATTERNS,
    PLATFORM_PATTERNS,
    PLATFORM_KEYWORDS,
    LEGAL_PATTERNS,
    DOCUMENT_PATTERNS,
    BUG_PATTERNS,
    GENERAL_KNOWLEDGE_PATTERNS,
    SOFT_DOCUMENT_PATTERN,
    USER_QUERY_PATTERNS,
    extract_resource_type,
)

logger = logging.getLogger(__name__)


@dataclass
class QueryClassification:
    """Immutable classification output."""

    intent: str  # one of the 7 intents
    language: str  # ar | fr | en
    confidence: float = 1.0  # 0.0–1.0
    qdrant_collections: List[str] = field(default_factory=list)
    qdrant_type_filter: Optional[str] = None  # payload "type" value
    use_postgresql: bool = False
    use_llm_direct: bool = False
    detected_resource_type: Optional[str] = (
        None  # extracted resource type (tool, course, …)
    )


class QueryClassifier:
    """Heuristic-based intent classifier for routing queries."""

    def __init__(self):
        self.lang_service = get_language_service()

    def classify(
        self,
        question: str,
        *,
        has_session_docs: bool = False,
    ) -> QueryClassification:
        """
        Classify a user question.

        Parameters
        ----------
        question : str
            Raw user input.
        has_session_docs : bool
            Whether the user has uploaded documents in the current session.
            Boosts document_query likelihood.

        Returns
        -------
        QueryClassification
        """
        language = self.lang_service.detect(question)
        q = question.strip()

        # --- 1. User identity / profile query ---
        if self._matches(q, USER_QUERY_PATTERNS):
            return QueryClassification(
                intent="user_query",
                language=language,
                confidence=0.90,
                use_postgresql=True,
            )

        # --- 2. Metadata query (stats, navigation) ---
        if self._matches(q, METADATA_PATTERNS):
            return QueryClassification(
                intent="metadata_query",
                language=language,
                confidence=0.90,
                use_postgresql=True,
            )

        # --- 3. Document query (user uploads) ---
        if self._matches(q, DOCUMENT_PATTERNS) or (
            has_session_docs and self._soft_document_hint(q)
        ):
            return QueryClassification(
                intent="document_query",
                language=language,
                confidence=0.85,
                qdrant_collections=["document_chunks"],
                qdrant_type_filter="document",
            )

        # --- 4. Legal query ---
        if self._matches(q, LEGAL_PATTERNS):
            return QueryClassification(
                intent="legal_query",
                language=language,
                confidence=0.85,
                qdrant_collections=["legal_documents"],
                qdrant_type_filter="law",
            )

        # --- 5. Bug query ---
        if self._matches(q, BUG_PATTERNS):
            return QueryClassification(
                intent="bug_query",
                language=language,
                confidence=0.80,
                qdrant_collections=["nlp_knowledge", "platform_docs"],
                qdrant_type_filter="bug",
            )

        # --- 6. Platform / structured query ---
        if self._matches(q, PLATFORM_PATTERNS) or self._has_platform_keywords(q):
            res_type = extract_resource_type(q)
            return QueryClassification(
                intent="platform_query",
                language=language,
                confidence=0.85,
                use_postgresql=True,
                detected_resource_type=res_type,
            )

        # --- 7. General knowledge (advice, plans, recommendations) → direct LLM ---
        if self._matches(q, GENERAL_KNOWLEDGE_PATTERNS):
            return QueryClassification(
                intent="general_knowledge",
                language=language,
                confidence=0.85,
                use_llm_direct=True,
            )

        # --- 8. Default: conceptual question → LLM with optional RAG ---
        return QueryClassification(
            intent="conceptual_question",
            language=language,
            confidence=0.70,
            qdrant_collections=["nlp_knowledge", "platform_docs", "resources"],
            use_llm_direct=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(text: str, patterns: list) -> bool:
        return any(p.search(text) for p in patterns)

    @staticmethod
    def _has_platform_keywords(text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in PLATFORM_KEYWORDS)

    @staticmethod
    def _soft_document_hint(text: str) -> bool:
        """Loose check when the user has docs and mentions summarise/explain etc."""
        return bool(SOFT_DOCUMENT_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_classifier: QueryClassifier | None = None


def get_query_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
