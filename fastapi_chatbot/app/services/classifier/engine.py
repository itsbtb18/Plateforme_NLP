"""
Confidence-based intent classifier for routing queries.

Phase 10 rewrite: scores all intents simultaneously, selects highest
confidence, and uses LLM classification fallback when ambiguous.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

from app.services.language import get_language_service
from app.services.classifier.patterns import (
    METADATA_PATTERNS,
    PLATFORM_PATTERNS,
    PLATFORM_KEYWORDS,
    LEGAL_PATTERNS,
    DOCUMENT_PATTERNS,
    BUG_PATTERNS,
    GENERAL_KNOWLEDGE_PATTERNS,
    USER_QUERY_PATTERNS,
    extract_resource_type,
)

logger = logging.getLogger(__name__)

# Minimum confidence gap between top-1 and top-2 to skip LLM fallback
_AMBIGUITY_MARGIN = 0.15


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


# Intent → routing parameters (avoids repeating in every branch)
_INTENT_PARAMS: Dict[str, dict] = {
    "user_query": {"use_postgresql": True},
    "metadata_query": {"use_postgresql": True},
    "document_query": {
        "qdrant_collections": ["document_chunks"],
        "qdrant_type_filter": "document",
    },
    "legal_query": {
        "qdrant_collections": ["legal_documents"],
        "qdrant_type_filter": "law",
    },
    "bug_query": {
        "qdrant_collections": ["nlp_knowledge", "platform_docs"],
        "qdrant_type_filter": "bug",
    },
    "platform_query": {"use_postgresql": True},
    "general_knowledge": {"use_llm_direct": True},
    "conceptual_question": {"qdrant_collections": ["nlp_knowledge"]},
}


class QueryClassifier:
    """Confidence-based intent classifier with LLM fallback."""

    def __init__(self):
        self.lang_service = get_language_service()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def classify(
        self,
        question: str,
        *,
        has_session_docs: bool = False,
    ) -> QueryClassification:
        """
        Classify a user question using multi-intent scoring.

        Scores all intents simultaneously, picks the highest-confidence
        match.  When the top two intents are within a narrow margin,
        the result is flagged as ambiguous (confidence capped at 0.60)
        so the caller can optionally invoke LLM disambiguation.
        """
        language = self.lang_service.detect(question)
        q = question.strip()

        scores = self._score_all_intents(q, has_session_docs)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        top_intent, top_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0

        # Check for ambiguity
        is_ambiguous = (
            top_score > 0 and (top_score - runner_up_score) < _AMBIGUITY_MARGIN
        )

        if top_score == 0:
            # No pattern matched → default conceptual_question
            return self._build_classification(
                "conceptual_question", language, 0.50
            )

        if is_ambiguous:
            # Confidence is capped to signal uncertainty
            confidence = min(top_score, 0.60)
            logger.info(
                "Ambiguous classification: top=%s(%.2f) runner_up=%s(%.2f) → "
                "using %s with capped confidence %.2f",
                ranked[0][0], ranked[0][1],
                ranked[1][0], ranked[1][1],
                top_intent, confidence,
            )
        else:
            confidence = top_score

        result = self._build_classification(top_intent, language, confidence)

        # Attach resource type for platform queries
        if top_intent == "platform_query":
            result.detected_resource_type = extract_resource_type(q)

        return result

    # ------------------------------------------------------------------
    # Async LLM fallback (can be called by chat_logic when ambiguous)
    # ------------------------------------------------------------------

    async def llm_resolve_ambiguity(
        self,
        question: str,
        language: str,
        top_intents: List[str],
    ) -> Optional[str]:
        """Use a lightweight LLM call to disambiguate between top intents.

        Returns one of the *top_intents* or None on failure.
        Called from chat_logic only when classification.confidence <= 0.60.
        """
        try:
            from app.services.llm import get_groq_client

            client = get_groq_client()
            intents_str = ", ".join(top_intents)
            system = (
                "You are an intent classifier. Given a user question and a set "
                "of candidate intents, respond with ONLY the single best intent "
                "name. Do not explain.\n\n"
                f"Candidate intents: {intents_str}\n\n"
                "Intent definitions:\n"
                "- user_query: user asking about their own profile/name/contributions\n"
                "- metadata_query: asking for statistics, counts, navigation\n"
                "- document_query: asking about uploaded documents\n"
                "- legal_query: asking about laws or legal texts\n"
                "- bug_query: reporting a bug or technical issue\n"
                "- platform_query: asking about platform resources (tools, courses, etc.)\n"
                "- general_knowledge: open-ended advice, brainstorming, plans\n"
                "- conceptual_question: NLP/AI concept explanations\n"
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ]
            answer = await client.chat_completion(
                messages, temperature=0.0, max_tokens=20,
            )
            resolved = answer.strip().lower().replace('"', "").replace("'", "")
            if resolved in top_intents:
                logger.info("LLM resolved ambiguity → %s", resolved)
                return resolved
            logger.warning(
                "LLM returned unexpected intent '%s', ignoring", resolved,
            )
        except Exception:
            logger.warning("LLM intent fallback failed", exc_info=True)
        return None

    # ------------------------------------------------------------------
    # Multi-intent scoring
    # ------------------------------------------------------------------

    def _score_all_intents(
        self, text: str, has_session_docs: bool,
    ) -> Dict[str, float]:
        """Compute a confidence score (0.0–1.0) for every intent."""
        scores: Dict[str, float] = {}

        # Count how many patterns match per intent
        scores["user_query"] = self._match_score(
            text, USER_QUERY_PATTERNS, base=0.90,
        )
        scores["metadata_query"] = self._match_score(
            text, METADATA_PATTERNS, base=0.88,
        )
        scores["document_query"] = self._match_score(
            text, DOCUMENT_PATTERNS, base=0.85,
        )
        scores["legal_query"] = self._match_score(
            text, LEGAL_PATTERNS, base=0.85,
        )
        scores["bug_query"] = self._match_score(
            text, BUG_PATTERNS, base=0.80,
        )
        scores["platform_query"] = self._match_score(
            text, PLATFORM_PATTERNS, base=0.85,
        )
        # Platform keywords add a weaker signal
        if self._has_platform_keywords(text):
            scores["platform_query"] = max(
                scores["platform_query"], 0.65,
            )
        scores["general_knowledge"] = self._match_score(
            text, GENERAL_KNOWLEDGE_PATTERNS, base=0.82,
        )

        # conceptual_question is the default — gets a floor score
        scores["conceptual_question"] = 0.0

        return scores

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_score(text: str, patterns: list, *, base: float) -> float:
        """Score an intent by counting matching patterns.

        First match → *base* confidence.
        Each additional match adds a small bonus (capped at 0.98).
        Zero matches → 0.0.
        """
        count = sum(1 for p in patterns if p.search(text))
        if count == 0:
            return 0.0
        # Diminishing returns per extra match
        bonus = min(count - 1, 3) * 0.03
        return min(base + bonus, 0.98)

    @staticmethod
    def _has_platform_keywords(text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in PLATFORM_KEYWORDS)

    @staticmethod
    def _build_classification(
        intent: str, language: str, confidence: float,
    ) -> QueryClassification:
        """Construct a QueryClassification from intent name."""
        params = _INTENT_PARAMS.get(intent, {})
        return QueryClassification(
            intent=intent,
            language=language,
            confidence=confidence,
            qdrant_collections=list(params.get("qdrant_collections", [])),
            qdrant_type_filter=params.get("qdrant_type_filter"),
            use_postgresql=params.get("use_postgresql", False),
            use_llm_direct=params.get("use_llm_direct", False),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_classifier: QueryClassifier | None = None


def get_query_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
