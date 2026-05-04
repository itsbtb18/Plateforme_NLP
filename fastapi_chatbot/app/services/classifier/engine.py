"""
Intent classifier — LLM zero-shot primary, regex fallback.

Phase 2 rewrite: LLM zero-shot classification is the primary method.
Regex patterns are kept as a fast-path for trivial cases (greetings,
identity) and as a fallback when the LLM call fails.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict

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
    CONTRIBUTOR_SEARCH_PATTERNS,
    extract_resource_type,
)

logger = logging.getLogger(__name__)

# Minimum confidence gap between top-1 and top-2 to skip LLM fallback
_AMBIGUITY_MARGIN = 0.15


@dataclass
class QueryClassification:
    """Immutable classification output."""

    intent: str  # one of the 8 intents
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
    # Memory intents — handled before retrieval, no RAG needed
    "memory_translate_last_user_query": {"use_llm_direct": True},
    "memory_translate_last_answer": {"use_llm_direct": True},
    "memory_repeat_last_user_query": {"use_llm_direct": True},
    "memory_summarize_last_answer": {"use_llm_direct": True},
    "memory_compare_last_two_queries": {"use_llm_direct": True},
}

# Greetings / short social messages — no LLM needed
_GREETING_RE = re.compile(
    r"^\s*(?:"
    r"hi|hello|hey|yo|hiya|howdy|greetings|good\s*(?:morning|afternoon|evening|day)|"
    r"thanks?(?:\s*you)?|thank\s*u|welcome|"
    r"bonjour|salut|bonsoir|coucou|bonne\s*(?:journée|soirée)|merci|"
    r"مرحبا|مرحبًا|سلام|أهلا|السلام عليكم|صباح الخير|مساء الخير|أهلاً|هلا|شكرا|شكراً"
    r")\s*[!?.]*\s*$",
    re.IGNORECASE,
)

# Chatbot identity — no LLM needed
_IDENTITY_RE = re.compile(
    r"(?:"
    r"\bwho are you\b|\bwhat are you\b|\btell me about yourself\b|\bintroduce yourself\b|"
    r"\bqui es[- ]tu\b|\bqu'es[- ]tu\b|\bprésentez?[- ](?:toi|vous)\b|"
    r"من أنت|ما أنت|عرّف (?:عن )?نفسك"
    r")",
    re.IGNORECASE,
)

# Pasted-result analysis prompts can contain words like "author"/"open"
# from UI cards and be misclassified as platform queries.
_ANALYZE_ANSWER_RE = re.compile(
    r"(?:\b(?:analy[sz]e|explain|interpret|review)\b|"
    r"\b(?:analyse|expliquer|interpr[eé]ter)\b|"
    r"(?:حلل|اشرح|فسر))"
    r".*"
    r"(?:\banswer\b|\br[eé]ponse\b|(?:الإجابة|الجواب))",
    re.IGNORECASE,
)

# Memory command patterns — AR/FR/EN (fast-path before LLM)
_MEMORY_TRANSLATE_RE = re.compile(
    r"(?:"
    r"\btranslat[e]\b.*\b(?:last|previous|my)\b.*\b(?:question|query|message)\b|"
    r"\b(?:last|previous|my)\b.*\b(?:question|query|message)\b.*\btranslat|"
    r"\btranslat[e]\b.*\b(?:last|previous|your|the)\b.*\b(?:answer|response|reply)\b|"
    r"\b(?:last|previous|your|the)\b.*\b(?:answer|response|reply)\b.*\btranslat|"
    r"\btradui[st]\b.*\b(?:derni[eè]re?)\b.*\b(?:question|requ[eê]te|message)\b|"
    r"\b(?:derni[eè]re?)\b.*\b(?:question|requ[eê]te)\b.*\btradui|"
    r"\btradui[st]\b.*\b(?:derni[eè]re?)\b.*\b(?:r[eé]ponse|answer)\b|"
    r"\b(?:derni[eè]re?)\b.*\b(?:r[eé]ponse|answer)\b.*\btradui|"
    r"ترجم.*(?:آخر|الأخير|سؤال)|"
    r"(?:آخر|الأخير).*سؤال.*ترجم|"
    r"ترجم.*(?:آخر|الأخيرة?).*(?:إجابة|رد)|"
    r"(?:آخر|الأخيرة?).*(?:إجابة|رد).*ترجم"
    r")",
    re.IGNORECASE,
)

_MEMORY_REPEAT_RE = re.compile(
    r"(?:"
    r"\b(?:repeat|show|what was)\b.*\b(?:last|previous|my)\b.*\b(?:question|query|message)\b|"
    r"\b(?:last|previous|my)\b.*\b(?:question|query)\b.*\b(?:was|repeat|show)\b|"
    r"\br[eé]p[eè]t[e]\b.*\b(?:derni[eè]re?)\b.*\b(?:question|requ[eê]te)\b|"
    r"\b(?:derni[eè]re?)\b.*\b(?:question|requ[eê]te)\b.*\br[eé]p[eè]t|"
    r"(?:أعد|كرر|ما هو).*(?:آخر|الأخير).*سؤال|"
    r"(?:آخر|الأخير).*سؤال.*(?:أعد|كرر)"
    r")",
    re.IGNORECASE,
)

_MEMORY_SUMMARIZE_RE = re.compile(
    r"(?:"
    r"\bsummari[sz]e\b.*\b(?:last|previous|your)\b.*\b(?:answer|response|reply)\b|"
    r"\b(?:last|previous|your)\b.*\b(?:answer|response|reply)\b.*\bsummari|"
    r"\br[eé]sum[eé]\b.*\b(?:derni[eè]re?)\b.*\b(?:r[eé]ponse|answer)\b|"
    r"\b(?:derni[eè]re?)\b.*\b(?:r[eé]ponse)\b.*\br[eé]sum|"
    r"(?:لخص|اختصر).*(?:آخر|الأخيرة?).*(?:إجابة|رد)|"
    r"(?:آخر|الأخيرة?).*(?:إجابة|رد).*(?:لخص|اختصر)"
    r")",
    re.IGNORECASE,
)

_MEMORY_COMPARE_RE = re.compile(
    r"(?:"
    r"\bcompar[e]\b.*\b(?:last|previous|my)\b.*\b(?:two|2)\b.*\b(?:question|quer)|"
    r"\b(?:last|previous)\b.*\b(?:two|2)\b.*\b(?:question|quer).*\bcompar|"
    r"\bcompar[e]\b.*\b(?:derni[eè]re?s?)\b.*\b(?:deux|2)\b.*\b(?:question|requ[eê]te)|"
    r"\bcompar[e]\b.*\b(?:deux|2)\b.*\b(?:derni[eè]re?s?)\b.*\b(?:question|requ[eê]te)|"
    r"\b(?:deux|2)\b.*\b(?:derni[eè]re?s?)\b.*\b(?:question|requ[eê]te).*\bcompar|"
    r"(?:قارن|قارني).*(?:آخر|الأخيرين).*سؤال|"
    r"(?:آخر|الأخيرين).*سؤال.*(?:قارن|قارني)"
    r")",
    re.IGNORECASE,
)

# Mapping from regex to memory intent name
_MEMORY_REGEX_MAP = [
    (_MEMORY_TRANSLATE_RE, "memory_translate_last_user_query"),
    (_MEMORY_REPEAT_RE, "memory_repeat_last_user_query"),
    (_MEMORY_SUMMARIZE_RE, "memory_summarize_last_answer"),
    (_MEMORY_COMPARE_RE, "memory_compare_last_two_queries"),
]


class QueryClassifier:
    """LLM zero-shot classifier with regex fast-path and fallback."""

    def __init__(self):
        self.lang_service = get_language_service()

    def _force_conceptual_for_answer_analysis(
        self,
        question: str,
        intent: str,
    ) -> bool:
        """Return True when a pasted-answer analysis should be conceptual.

        This avoids routing to platform search just because pasted snippets
        include UI terms such as "author" and "open".
        """
        if intent != "platform_query":
            return False
        q = question.strip()
        return len(q) >= 80 and bool(_ANALYZE_ANSWER_RE.search(q))

    def _force_legal_when_explicit(self, question: str, intent: str) -> bool:
        """Return True when legal lexical signals should override intent.

        This protects legal questions that mention platform entities
        (Academia/ResearchGate/author) from being misrouted to platform_query.
        """
        if intent == "legal_query":
            return False
        q = question.strip()
        # Require at least one explicit legal marker.
        return any(p.search(q) for p in LEGAL_PATTERNS)

    # ------------------------------------------------------------------
    # Synchronous fast-path (no LLM needed for trivial queries)
    # ------------------------------------------------------------------

    def classify_fast(self, question: str) -> Optional[QueryClassification]:
        """Fast regex-only classification for trivial cases.

        Returns a classification for greetings and identity questions,
        or None if LLM classification is needed.
        """
        q = question.strip()
        language = self.lang_service.detect(q)

        # Greetings → general_knowledge (no retrieval needed)
        if _GREETING_RE.match(q):
<<<<<<< HEAD
            return self._build_classification("general_knowledge", language, 0.99, q)

        # Identity questions → general_knowledge
        if _IDENTITY_RE.search(q):
            return self._build_classification("general_knowledge", language, 0.99, q)
=======
            return self._build_classification("general_knowledge", language, 0.99)

        # Identity questions → general_knowledge
        if _IDENTITY_RE.search(q):
            return self._build_classification("general_knowledge", language, 0.99)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        # Memory commands → no retrieval needed (fast-path)
        for regex, intent_name in _MEMORY_REGEX_MAP:
            if regex.search(q):
                resolved_intent = intent_name
                if (
                    intent_name == "memory_translate_last_user_query"
                    and re.search(
                        r"\b(?:answer|response|reply|r[eé]ponse)\b|(?:إجابة|رد)",
                        q,
                        re.IGNORECASE,
                    )
                ):
                    resolved_intent = "memory_translate_last_answer"
                logger.info(
                    "Memory intent fast-path: %s for query '%s'",
                    resolved_intent, q[:60],
                )
<<<<<<< HEAD
                return self._build_classification(resolved_intent, language, 0.97, q)
=======
                return self._build_classification(resolved_intent, language, 0.97)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        return None

    # ------------------------------------------------------------------
    # Synchronous classify (regex scoring — kept as fallback)
    # ------------------------------------------------------------------

    def classify(
        self,
        question: str,
        *,
        has_session_docs: bool = False,
    ) -> QueryClassification:
        """Classify using regex patterns — used as fallback when LLM fails.

        Scores all intents simultaneously, picks the highest-confidence
        match.  When the top two intents are within a narrow margin,
        the result is flagged as ambiguous (confidence capped at 0.60).
        """
        language = self.lang_service.detect(question)
        q = question.strip()

        # Try fast-path first
        fast = self.classify_fast(q)
        if fast:
            return fast

        scores = self._score_all_intents(q, has_session_docs)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        top_intent, top_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0

        _AMBIGUITY_MARGIN = 0.15
        is_ambiguous = (
            top_score > 0 and (top_score - runner_up_score) < _AMBIGUITY_MARGIN
        )

        if top_score == 0:
<<<<<<< HEAD
            return self._build_classification("conceptual_question", language, 0.50, q)
=======
            return self._build_classification("conceptual_question", language, 0.50)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        if is_ambiguous:
            confidence = min(top_score, 0.60)
            logger.info(
                "Ambiguous classification (regex fallback): top=%s(%.2f) "
                "runner_up=%s(%.2f) → using %s with capped confidence %.2f",
                ranked[0][0], ranked[0][1],
                ranked[1][0], ranked[1][1],
                top_intent, confidence,
            )
        else:
            confidence = top_score

<<<<<<< HEAD
        result = self._build_classification(top_intent, language, confidence, q)
=======
        result = self._build_classification(top_intent, language, confidence)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        if self._force_legal_when_explicit(q, result.intent):
            logger.info(
                "Classifier correction: forcing legal_query for explicit legal wording"
            )
<<<<<<< HEAD
            return self._build_classification("legal_query", language, 0.90, q)

        if self._force_conceptual_for_answer_analysis(q, result.intent):
            return self._build_classification("conceptual_question", language, 0.80, q)
=======
            return self._build_classification("legal_query", language, 0.90)

        if self._force_conceptual_for_answer_analysis(q, result.intent):
            return self._build_classification("conceptual_question", language, 0.80)

        if top_intent == "platform_query":
            result.detected_resource_type = extract_resource_type(q)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        return result

    # ------------------------------------------------------------------
    # Async LLM zero-shot classification (PRIMARY method)
    # ------------------------------------------------------------------

    async def classify_with_llm(
        self,
        question: str,
        *,
        has_session_docs: bool = False,
    ) -> QueryClassification:
        """Primary classification using LLM zero-shot.

        Falls back to regex-based classify() on LLM failure.
        """
        language = self.lang_service.detect(question)
        q = question.strip()

        # Fast-path for trivial queries (no LLM call needed)
        fast = self.classify_fast(q)
        if fast:
            return fast

        # LLM zero-shot classification
        try:
            from app.services.llm import get_internal_llm_client
            from app.services.llm.prompts import VALID_INTENTS

            client = get_internal_llm_client()
            labels = ", ".join(sorted(VALID_INTENTS))
            prompt = (
                "Classify this query into exactly one intent label. "
                "Return only the label, no explanation.\n"
                f"Allowed labels: {labels}\n"
                f"Query: {q}\n"
                "Label:"
            )

            response = await client.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=16,
            )

            raw = (response or "").strip().lower()
            intent = (
                raw.replace('"', "")
                .replace("'", "")
                .replace("`", "")
                .replace("-", "_")
                .replace(" ", "_")
                .replace(".", "")
                .strip("_")
            )

            alias_map = {
                "conceptual": "conceptual_question",
                "concept": "conceptual_question",
                "general": "general_knowledge",
                "knowledge": "general_knowledge",
                "platform": "platform_query",
                "metadata": "metadata_query",
                "document": "document_query",
                "legal": "legal_query",
                "bug": "bug_query",
                "user": "user_query",
            }
            intent = alias_map.get(intent, intent)

            if intent not in VALID_INTENTS:
                # Accept outputs like "intent: conceptual_question".
                intent_scan = re.sub(r"[^a-z_]", " ", raw).replace(" ", "_")
                for valid_intent in VALID_INTENTS:
                    if valid_intent in intent_scan:
                        intent = valid_intent
                        break

            if intent in VALID_INTENTS:
                logger.info(
                    "LLM classification: query='%s' → intent=%s lang=%s",
                    q[:60], intent, language,
                )
<<<<<<< HEAD
                result = self._build_classification(intent, language, 0.95, q)
=======
                result = self._build_classification(intent, language, 0.95)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

                if self._force_legal_when_explicit(q, result.intent):
                    logger.info(
                        "Classifier correction: forcing legal_query for explicit legal wording"
                    )
                    return self._build_classification(
<<<<<<< HEAD
                        "legal_query", language, 0.92, q
=======
                        "legal_query", language, 0.92,
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                    )

                if self._force_conceptual_for_answer_analysis(q, result.intent):
                    logger.info(
                        "Classifier correction: forcing conceptual_question "
                        "for pasted-answer analysis query"
                    )
                    return self._build_classification(
<<<<<<< HEAD
                        "conceptual_question", language, 0.90, q
                    )

=======
                        "conceptual_question", language, 0.90,
                    )

                if intent == "platform_query":
                    result.detected_resource_type = extract_resource_type(q)

>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                return result
            else:
                logger.warning(
                    "LLM returned invalid intent '%s' for query '%s', "
                    "falling back to regex",
                    intent, q[:60],
                )

        except Exception as e:
            logger.warning(
                "LLM classification failed (%s), falling back to regex",
                type(e).__name__,
            )

        # Fallback to regex-based classification
        return self.classify(question, has_session_docs=has_session_docs)

    # ------------------------------------------------------------------
    # Async LLM disambiguation (kept for backward compat)
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
            from app.services.llm import get_llm_client

            client = get_llm_client()
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
    # Multi-intent scoring (regex-based, kept as fallback)
    # ------------------------------------------------------------------

    def _score_all_intents(
        self, text: str, has_session_docs: bool,
    ) -> Dict[str, float]:
        """Compute a confidence score (0.0–1.0) for every intent."""
        scores: Dict[str, float] = {}

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
        scores["platform_query"] = max(
            scores["platform_query"],
            self._match_score(text, CONTRIBUTOR_SEARCH_PATTERNS, base=0.92)
        )
        scores["general_knowledge"] = self._match_score(
            text, GENERAL_KNOWLEDGE_PATTERNS, base=0.82,
        )
        if self._has_platform_keywords(text) and scores["general_knowledge"] == 0.0 and scores["legal_query"] == 0.0:
            scores["platform_query"] = max(
                scores["platform_query"], 0.65,
            )

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
        bonus = min(count - 1, 3) * 0.03
        return min(base + bonus, 0.98)

    @staticmethod
    def _has_platform_keywords(text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in PLATFORM_KEYWORDS)

<<<<<<< HEAD
    def _build_classification(
        self,
        intent: str,
        language: str,
        confidence: float,
        text: Optional[str] = None,
    ) -> QueryClassification:
        """Construct a QueryClassification from intent name."""
        params = _INTENT_PARAMS.get(intent, {})
        cls = QueryClassification(
=======
    @staticmethod
    def _build_classification(
        intent: str, language: str, confidence: float,
    ) -> QueryClassification:
        """Construct a QueryClassification from intent name."""
        params = _INTENT_PARAMS.get(intent, {})
        return QueryClassification(
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            intent=intent,
            language=language,
            confidence=confidence,
            qdrant_collections=list(params.get("qdrant_collections", [])),
            qdrant_type_filter=params.get("qdrant_type_filter"),
            use_postgresql=params.get("use_postgresql", False),
            use_llm_direct=params.get("use_llm_direct", False),
        )
<<<<<<< HEAD
        if intent == "platform_query" and text:
            cls.detected_resource_type = extract_resource_type(text)
        return cls
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_classifier: Optional[QueryClassifier] = None


def get_query_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
