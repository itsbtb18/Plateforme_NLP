"""
Query router — directs classified queries to the correct data source.

Routing rules:
  - conceptual_question → Qdrant semantic search (broad) → Groq LLM
  - platform_query      → PostgreSQL (platform_queries service)
  - legal_query         → Qdrant with type=law / language filter
  - document_query      → Qdrant with owner_id / session filter
  - bug_query           → Qdrant with type=bug filter
  - metadata_query      → PostgreSQL (stats / navigation)
  - web (Exa fallback)  → triggered when confidence < 0.50 for legal/NLP intents
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.classifier.engine import QueryClassification
from app.services.retrieval import (
    hybrid_search,
    search_platform_docs,
    search_nlp_knowledge,
    search_resources,
    search_legal_documents,
    search_user_documents,
)
from app.services.platform_queries import get_platform_query_service
from app.services.elasticsearch_service import get_elasticsearch_service
from app.services.web.confidence import (
    compute_retrieval_confidence,
    should_trigger_exa,
    should_use_web_only_context,
)
from app.services.web.exa_client import search_exa
from app.services.web.cache import cache_get, cache_set
from app.services.web.policy import get_exa_policy
from app.services.llm.client import get_chat_provider_label
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
LLM_SOURCE_LABEL = get_chat_provider_label()

# ---------------------------------------------------------------------------
# Phase 3: Explicit intent → route mapping (documentation only).
# The actual routing logic is in QueryRouter.route(), but this table
# provides a single reference for understanding the intent→source mapping.
# ---------------------------------------------------------------------------
ROUTING_TABLE = {
    "general_knowledge":   {"source": LLM_SOURCE_LABEL, "retrieval": None,             "note": "Direct LLM, no retrieval"},
    "user_query":          {"source": "postgresql",  "retrieval": "platform_qs",    "note": "PostgreSQL user lookup"},
    "metadata_query":      {"source": "postgresql",  "retrieval": "platform_qs",    "note": "Stats, counts, navigation"},
    "platform_query":      {"source": "postgresql",  "retrieval": "platform_qs",    "note": "Platform resources search"},
    "conceptual_question": {"source": "qdrant",      "retrieval": "hybrid_search",  "note": "Dense + BM25 → semantic knowledge"},
    "legal_query":         {"source": "qdrant",      "retrieval": "legal_search",   "note": "Dense + BM25 → legal documents"},
    "document_query":      {"source": "qdrant",      "retrieval": "user_doc_search","note": "User uploaded docs"},
    "bug_query":           {"source": "qdrant",      "retrieval": "hybrid_search",  "note": "Bug-related knowledge"},
    "web_fallback":        {"source": "web_exa",     "retrieval": "exa_search",     "note": "Exa web fallback (low conf legal/NLP)"},
}



# ---------------------------------------------------------------------------
# Routing result
# ---------------------------------------------------------------------------


@dataclass
class RoutingResult:
    """Aggregated retrieval result returned by the router."""

    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    platform_results: List[Dict[str, Any]] = field(default_factory=list)
    primary_source: str = "none"
    skip_retrieval: bool = False  # True when LLM-direct is sufficient
    nav_hints: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class QueryRouter:
    """Route queries to PostgreSQL, Qdrant, or direct-LLM based on intent."""

    def __init__(self):
        self.platform_qs = get_platform_query_service()
        self.es_service = get_elasticsearch_service()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def route(
        self,
        question: str,
        classification: QueryClassification,
        db: AsyncSession,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None,
        document_id: Optional[int] = None,
        user_email: Optional[str] = None,
        on_exa_fallback: Optional[Callable[[], Awaitable[None]]] = None,
        mode: Optional[str] = None,
    ) -> RoutingResult:
        """Execute the retrieval strategy dictated by *classification*."""

        intent = classification.intent
        lang = classification.language
        result = RoutingResult()

        logger.info(
            "Routing: intent=%s lang=%s confidence=%.2f",
            intent,
            lang,
            classification.confidence,
        )

        # ----- Phase 3: Strict LLM-direct mode -----
        # When the classifier says use_llm_direct, skip ALL retrieval
        # (Qdrant, Elasticsearch, PostgreSQL).  This covers greetings,
        # conversational advice, brainstorming, and general knowledge.
        if classification.use_llm_direct:
            # Balanced behavior for factual lookups: try local vector search first,
            # then trigger Exa only when local retrieval is weak.
            if intent == "general_knowledge" and self._is_fact_lookup_question(question):
                docs, src = await self._semantic_targeted(
                    question,
                    db,
                    lang,
                    collections=["nlp_knowledge", "platform_docs"],
                    top_k=settings.TOP_K_RESULTS,
                )
                result.retrieved_docs = docs
                result.primary_source = src if docs else "none"

                exa_docs = await self._maybe_exa_fallback(
                    question,
                    docs,
                    "general_knowledge",
                    lang,
                    session_id=session_id,
                    user_id=user_id,
                    on_exa_fallback=on_exa_fallback,
                    mode=mode,
                )
                if exa_docs:
                    if should_use_web_only_context(docs, question, "conceptual_question"):
                        result.retrieved_docs = list(exa_docs)[: settings.TOP_K_RESULTS]
                    else:
                        combined_docs = list(exa_docs) + list(docs or [])
                        combined_docs.sort(
                            key=lambda d: float(d.get("similarity", 0.0)),
                            reverse=True,
                        )
                        result.retrieved_docs = combined_docs[: settings.TOP_K_RESULTS]
                    result.primary_source = "web_exa"

                if not result.retrieved_docs:
                    result.skip_retrieval = True
                    result.primary_source = LLM_SOURCE_LABEL
                return result

            result.skip_retrieval = True
            result.primary_source = LLM_SOURCE_LABEL
            return result

        # ----- user_query → self-only PostgreSQL user lookup -----
        if intent == "user_query":
            if user_email:
                # Self-referencing query only
                content_type = self._extract_content_type(question)
                is_identity_only = self._is_identity_question(question)
                if not is_identity_only:
                    contribs = await self.platform_qs.get_current_user_contributions(
                        db=db,
                        user_email=user_email,
                        content_type=content_type,
                    )
                    if contribs:
                        result.platform_results = [
                            {"type": "my_contributions", **contribs}
                        ]
                        result.primary_source = "platform"
                    else:
                        type_label = content_type or "content"
                        result.platform_results = [
                            {
                                "type": "no_data",
                                "message": (
                                    f"The current user has not created any {type_label}s "
                                    f"on the platform yet. The database returned zero results "
                                    f"for this user's contributions."
                                ),
                            }
                        ]
                        result.primary_source = "platform"
            # If no user_email or identity-only, LLM answers using profile context
            if not result.platform_results:
                result.primary_source = "platform"
                result.skip_retrieval = True
            return result

        # ----- conceptual_question → Qdrant (nlp_knowledge only by default) -----
        if intent == "conceptual_question":
            # Phase 2: Only search nlp_knowledge unless the query
            # explicitly asks for platform entities (courses, tools, etc.)
            collections = ["nlp_knowledge"]
            if self._wants_platform_entities(question):
                collections.extend(["platform_docs", "resources"])

            docs, src = await self._semantic_targeted(
                question,
                db,
                lang,
                collections=collections,
                top_k=settings.TOP_K_RESULTS,
            )
            result.retrieved_docs = docs
            result.primary_source = src

            # ── Exa fallback: augment when retrieval confidence is low ──
            exa_docs = await self._maybe_exa_fallback(
                question, docs, intent, lang,
                session_id=session_id, user_id=user_id,
                on_exa_fallback=on_exa_fallback,
                mode=mode,
            )
            if exa_docs:
                if should_use_web_only_context(docs, question, intent):
                    result.retrieved_docs = list(exa_docs)[: settings.TOP_K_RESULTS]
                else:
                    combined_docs = list(exa_docs) + list(docs or [])
                    combined_docs.sort(
                        key=lambda d: float(d.get("similarity", 0.0)),
                        reverse=True,
                    )
                    result.retrieved_docs = combined_docs[: settings.TOP_K_RESULTS]
                # Mark web_exa as the primary source whenever Exa docs are used
                # so downstream generation and UI attribution stay truthful.
                result.primary_source = "web_exa"

            if not result.retrieved_docs:
                result.skip_retrieval = True
                result.primary_source = LLM_SOURCE_LABEL
            return result

        # ----- platform_query → type-filtered search -----
        if intent == "platform_query":
            res_type = classification.detected_resource_type

            if res_type:
                # Type-specific search — only return the requested type
                if res_type == "author":
                    platform = await self.platform_qs.search_authors(
                        db=db,
                        keyword=None,
                        limit=10,
                    )
                else:
                    # Use type-specific ES index if available
                    es_index_map = {
                        "tool": ["nlp_tools"],
                        "course": ["courses"],
                        "corpus": ["corpora"],
                        "article": ["resources"],
                        "thesis": ["resources"],
                        "memoir": ["resources"],
                        "event": ["events"],
                        "institution": ["institutions"],
                        "project": ["projects"],
                        "topic": None,  # no ES index → PostgreSQL only
                        "forum": None,
                    }
                    indices = es_index_map.get(res_type)
                    if indices is None and res_type in (
                        "topic",
                        "forum",
                        "forum_topic",
                    ):
                        # Forum has no ES index — go straight to PostgreSQL
                        platform = await self.platform_qs.search_by_type(
                            db=db,
                            keyword=question,
                            resource_type=res_type,
                            limit=10,
                        )
                    else:
                        try:
                            platform = await self.es_service.search(
                                question,
                                indices=indices,
                                total_limit=10,
                            )
                        except Exception:
                            logger.warning(
                                "ES type-filtered search failed, PostgreSQL fallback",
                                exc_info=True,
                            )
                            platform = await self.platform_qs.search_by_type(
                                db=db,
                                keyword=question,
                                resource_type=res_type,
                                limit=10,
                            )
            else:
                # No specific type detected — broad search
                try:
                    platform = await self.es_service.search(
                        question,
                        total_limit=10,
                    )
                except Exception:
                    logger.warning(
                        "ES search failed, PostgreSQL fallback", exc_info=True
                    )
                    platform = await self.platform_qs.unified_search(
                        db=db,
                        keyword=question,
                        limit=10,
                    )

            if platform:
                result.platform_results = platform
                result.primary_source = "platform"
            else:
                # Tell the LLM explicitly that the platform has no matching data
                type_label = res_type or "content"
                result.platform_results = [
                    {
                        "type": "no_data",
                        "message": (
                            f"No {type_label}s were found on the platform. "
                            f"The database and search indices returned zero results "
                            f"for this query. The platform may not have any "
                            f"{type_label}s added yet."
                        ),
                    }
                ]
                result.primary_source = "platform"
            # Keep platform_query responses clean: do not attach semantic NLP docs
            # when platform cards are already returned, to avoid mixed/confusing sources.
            if not platform:
                docs, _ = await self._semantic_targeted(
                    question,
                    db,
                    lang,
                    collections=["platform_docs", "nlp_knowledge"],
                    top_k=3,
                )
                result.retrieved_docs = docs
            return result

        # ----- legal_query → Qdrant (law filter + same-language priority) -----
        if intent == "legal_query":
            docs = await search_legal_documents(
                query=question,
                db=db,
                top_k=settings.TOP_K_RESULTS,
            )
            result.retrieved_docs = docs
            result.primary_source = "legal" if docs else "none"

            # ── Exa fallback: augment when retrieval confidence is low ──
            exa_docs = await self._maybe_exa_fallback(
                question, docs, intent, lang,
                session_id=session_id, user_id=user_id,
                on_exa_fallback=on_exa_fallback,
                mode=mode,
            )
            if exa_docs:
                if should_use_web_only_context(docs, question, intent):
                    result.retrieved_docs = list(exa_docs)[: settings.TOP_K_RESULTS]
                else:
                    combined_docs = list(exa_docs) + list(docs or [])
                    combined_docs.sort(
                        key=lambda d: float(d.get("similarity", 0.0)),
                        reverse=True,
                    )
                    result.retrieved_docs = combined_docs[: settings.TOP_K_RESULTS]
                result.primary_source = "web_exa"

            return result

        # ----- document_query → Qdrant (user doc chunks, owner_id filter) -----
        if intent == "document_query":
            if session_id:
                docs = await search_user_documents(
                    query=question,
                    db=db,
                    session_id=session_id,
                    document_id=document_id,
                    owner_id=user_id,
                )
                result.retrieved_docs = docs
                result.primary_source = "user_document" if docs else "none"
            else:
                result.skip_retrieval = True
                result.primary_source = LLM_SOURCE_LABEL
            return result

        # ----- bug_query → Qdrant (nlp_knowledge + platform_docs) -----
        if intent == "bug_query":
            docs, src = await self._semantic_targeted(
                question,
                db,
                lang,
                collections=["nlp_knowledge", "platform_docs"],
                top_k=settings.TOP_K_RESULTS,
            )
            result.retrieved_docs = docs
            result.primary_source = src if docs else LLM_SOURCE_LABEL
            return result

        # ----- metadata_query → PostgreSQL stats + navigation -----
        if intent == "metadata_query":
            stats = await self.platform_qs.get_platform_stats(db)
            nav = await self.platform_qs.get_navigation_help(question)

            if stats:
                result.platform_results.append({"type": "stats", **stats})
            if nav and nav.get("suggestions"):
                result.nav_hints = nav

            result.primary_source = "platform" if result.platform_results else "none"
            return result

        # Fallback
        logger.warning("Unknown intent %s — falling back to broad search", intent)
        docs, src = await self._semantic_broad(
            question,
            db,
            lang,
            user_country=user_country,
            user_city=user_city,
        )
        result.retrieved_docs = docs
        result.primary_source = src
        return result

    # ------------------------------------------------------------------
    # Internal retrieval strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _is_identity_question(question: str) -> bool:
        """Return True if the question is purely about the user's identity
        (name, bio, who am I) and NOT about their contributions."""
        import re

        q = question.lower().strip()
        identity_patterns = [
            r"\b(?:what(?:'?s| is)\s+my\s+name)\b",
            r"\bwhats my name\b",
            r"\bwho\s+am\s+i\b",
            r"\btell\s+me\s+(?:my\s+name|about\s+me|about\s+myself)\b",
            r"\bما\s*(?:هو\s*)?اسمي\b",
            r"\bمن\s*أنا\b",
            r"\bquel\s+est\s+mon\s+nom\b",
            r"\bcomment\s+(?:je\s+m'appelle|m'appelle)\b",
            r"\bqui\s+suis[- ]je\b",
        ]
        for pat in identity_patterns:
            if re.search(pat, q):
                return True
        return False

    @staticmethod
    def _extract_content_type(question: str) -> Optional[str]:
        """Detect if the user is asking about a specific content type they own.

        Returns a content_type string matching the platform_queries parameter,
        or None for 'all contributions'.
        """
        import re

        q = question.lower()
        mapping = {
            "tool": r"\btool",
            "course": r"\bcours",
            "post": r"\bpost",
            "document": r"\b(?:document|article|thesis|memoir|publication)",
            "article": r"\barticle",
            "thesis": r"\bthes[ie]s",
            "memoir": r"\bmemoir",
            "corpus": r"\bcorpu",
            "project": r"\bproject",
            "event": r"\bevent",
            "question": r"\bquestion",
            "answer": r"\banswer",
            "topic": r"\btopic",
        }
        for ctype, pattern in mapping.items():
            if re.search(pattern, q):
                return ctype
        # French
        fr_map = {
            "tool": r"\boutils?\b",
            "course": r"\bcours\b",
            "post": r"\b(?:post|publication)s?\b",
            "project": r"\bprojets?\b",
            "document": r"\b(?:documents?|articles?)\b",
        }
        for ctype, pattern in fr_map.items():
            if re.search(pattern, q):
                return ctype
        # Arabic
        ar_map = {
            "tool": "أدوات",
            "course": "دورات",
            "post": "منشورات",
            "project": "مشاريع",
            "document": "مقالات",
        }
        for ctype, word in ar_map.items():
            if word in q:
                return ctype
        return None

    @staticmethod
    def _wants_platform_entities(question: str) -> bool:
        """Return True if the question explicitly asks for platform entities
        (courses, tools, institutions, resources, recommendations, etc.)."""
        import re
        q = question.lower()
        return bool(re.search(
            r"\b(?:course|cours|دور[اة]|tool|outil|أدا[ةت]|institution|مؤسس|"
            r"recommend|suggest|where.+(?:study|learn)|show.+resource|"
            r"programme?|program|formation)\b",
            q,
        ))

    @staticmethod
    def _is_fact_lookup_question(question: str) -> bool:
        """Detect short factual lookup prompts suitable for RAG+Exa balancing."""
        import re

        q = (question or "").strip().lower()
        return bool(
            re.search(
                r"^(?:who\s+is|what\s+is|tell\s+me\s+(?:about|how|what)|"
                r"explain(?:\s+to\s+me)?\s+(?:what\s+is|how|who|why)|"
                r"من\s+هو|ما\s+هو|c'?est\s+quoi|qui\s+est)\b",
                q,
            )
        )

    async def _semantic_broad(
        self,
        question: str,
        db: AsyncSession,
        language: str,
        *,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None,
    ) -> tuple[List[Dict], str]:
        """Search across all Qdrant collections (hybrid_search)."""
        return await hybrid_search(
            query=question,
            db=db,
            user_country=user_country,
            user_city=user_city,
            include_legal=True,
            language=language,
        )

    # Phase 7: Per-collection similarity thresholds.
    # Avoids weak / irrelevant matches from polluting the LLM context.
    _COLLECTION_THRESHOLDS: Dict[str, float] = {
        "document_chunks": 0.65,
        "legal_documents": 0.45,  # Lowered from 0.60 to improve Legal Advisor coverage
        # NLP queries with typos/noisy wording often score around 0.47-0.52.
        # Some valid conceptual queries score around 0.40-0.44 in this corpus.
        # 0.35 reduces unnecessary non-RAG fallbacks while keeping weak noise out.
        "nlp_knowledge": 0.35,
        "platform_docs": 0.50,
        "resources": 0.50,
    }

    async def _semantic_targeted(
        self,
        question: str,
        db: AsyncSession,
        language: str,
        *,
        collections: List[str],
        top_k: int = 5,
    ) -> tuple[List[Dict], str]:
        """Search only the specified Qdrant collections."""
        all_docs: List[Dict] = []
        per_collection_k = max(2, top_k // len(collections))

        for coll_name in collections:
            if coll_name == "platform_docs":
                docs = await search_platform_docs(
                    question,
                    db,
                    top_k=per_collection_k,
                )
            elif coll_name == "nlp_knowledge":
                docs = await search_nlp_knowledge(
                    question,
                    db,
                    top_k=per_collection_k,
                    language=language,
                )
            elif coll_name == "resources":
                docs = await search_resources(
                    question,
                    db,
                    top_k=per_collection_k,
                )
            elif coll_name == "legal_documents":
                docs = await search_legal_documents(
                    question,
                    db,
                    top_k=per_collection_k,
                )
            else:
                continue
            # Phase 7: Apply per-collection similarity floor
            threshold = self._COLLECTION_THRESHOLDS.get(coll_name)
            if threshold is not None:
                docs = [d for d in docs if d.get("similarity", 0) >= threshold]
            all_docs.extend(docs)

        all_docs.sort(key=lambda d: d.get("similarity", 0), reverse=True)
        top = all_docs[:top_k]
        primary = top[0]["source"] if top else "none"
        return top, primary

    # ------------------------------------------------------------------
    # Exa web fallback (Phase: Web Search Upgrade)
    # ------------------------------------------------------------------

    async def _maybe_exa_fallback(
        self,
        question: str,
        retrieved_docs: List[Dict],
        intent: str,
        language: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        on_exa_fallback: Optional[Callable[[], Awaitable[None]]] = None,
        mode: Optional[str] = None,
    ) -> List[Dict]:
        """Check retrieval confidence and call Exa if below threshold.

        Returns extra docs from Exa (empty list if not triggered).
        """
        if not settings.EXA_ENABLED:
            return []

        confidence = compute_retrieval_confidence(retrieved_docs)
        if not should_trigger_exa(confidence, intent, retrieved_docs, question, mode=mode):
            logger.info(
                "Exa fallback NOT triggered: confidence=%.3f intent=%s",
                confidence, intent,
            )
            return []

        # Check cache first
        cached = cache_get(question, intent, language)
        if cached is not None:
            if on_exa_fallback:
                try:
                    await on_exa_fallback()
                except Exception as e:
                    logger.error("Error in on_exa_fallback (cache hit): %s", e)
            logger.info(
                "Exa fallback: using %d cached results (intent=%s)",
                len(cached), intent,
            )
            return cached

        # Check budget
        policy = get_exa_policy()
        allowed, reason = policy.can_call(session_id=session_id, user_id=user_id)
        if not allowed:
            logger.info(
                "Exa fallback SKIPPED (budget): %s confidence=%.3f",
                reason, confidence,
            )
            return []

        # Call Exa
        logger.info(
            "Exa fallback TRIGGERED: confidence=%.3f intent=%s query='%s'",
            confidence, intent, question[:60],
        )
        if on_exa_fallback:
            try:
                await on_exa_fallback()
            except Exception as e:
                logger.error("Error in on_exa_fallback: %s", e)
                
        start = time.monotonic()
        exa_docs = await search_exa(question, intent=intent, language=language)
        latency = time.monotonic() - start

        # Record call and cache results
        policy.record_call(session_id=session_id, user_id=user_id)
        if exa_docs:
            cache_set(question, intent, language, exa_docs)

        logger.info(
            "Exa fallback complete: docs=%d latency=%.2fs cache_hit=false "
            "intent=%s confidence=%.3f",
            len(exa_docs), latency, intent, confidence,
        )
        return exa_docs


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_router: QueryRouter | None = None


def get_query_router() -> QueryRouter:
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router
