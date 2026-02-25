"""
Query router — directs classified queries to the correct data source.

Routing rules:
  - conceptual_question → Qdrant semantic search (broad) → Groq LLM
  - platform_query      → PostgreSQL (platform_queries service)
  - legal_query         → Qdrant with type=law / language filter
  - document_query      → Qdrant with owner_id / session filter
  - bug_query           → Qdrant with type=bug filter
  - metadata_query      → PostgreSQL (stats / navigation)
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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
    ) -> RoutingResult:
        """Execute the retrieval strategy dictated by *classification*."""

        intent = classification.intent
        lang = classification.language
        result = RoutingResult()

        logger.info(
            "Routing: intent=%s lang=%s confidence=%.2f",
            intent, lang, classification.confidence,
        )

        # ----- general_knowledge → direct LLM, no retrieval -----
        if intent == "general_knowledge":
            result.skip_retrieval = True
            result.primary_source = "groq"
            return result

        # ----- conceptual_question → broad Qdrant + optional LLM-direct -----
        if intent == "conceptual_question":
            docs, src = await self._semantic_broad(
                question, db, lang,
                user_country=user_country, user_city=user_city,
            )
            result.retrieved_docs = docs
            result.primary_source = src
            if not docs:
                result.skip_retrieval = True
                result.primary_source = "groq"
            return result

        # ----- platform_query → Elasticsearch + optional Qdrant -----
        if intent == "platform_query":
            try:
                platform = await self.es_service.search(
                    question, total_limit=10,
                )
            except Exception:
                logger.warning(
                    "ES search failed, falling back to PostgreSQL", exc_info=True,
                )
                platform = await self.platform_qs.unified_search(
                    db=db, keyword=question, limit=10,
                )
            result.platform_results = platform
            result.primary_source = "platform" if platform else "none"
            docs, _ = await self._semantic_targeted(
                question, db, lang,
                collections=["platform_docs", "nlp_knowledge"],
                top_k=3,
            )
            result.retrieved_docs = docs
            return result

        # ----- legal_query → Qdrant (law filter + same-language priority) -----
        if intent == "legal_query":
            docs = await search_legal_documents(
                query=question, db=db, top_k=settings.TOP_K_RESULTS,
                language=lang,
            )
            result.retrieved_docs = docs
            result.primary_source = "legal" if docs else "none"
            return result

        # ----- document_query → Qdrant (user doc chunks, owner_id filter) -----
        if intent == "document_query":
            if session_id:
                docs = await search_user_documents(
                    query=question, db=db,
                    session_id=session_id,
                    document_id=document_id,
                    owner_id=user_id,
                )
                result.retrieved_docs = docs
                result.primary_source = "user_document" if docs else "none"
            else:
                result.skip_retrieval = True
                result.primary_source = "groq"
            return result

        # ----- bug_query → Qdrant (nlp_knowledge + platform_docs) -----
        if intent == "bug_query":
            docs, src = await self._semantic_targeted(
                question, db, lang,
                collections=["nlp_knowledge", "platform_docs"],
                top_k=settings.TOP_K_RESULTS,
            )
            result.retrieved_docs = docs
            result.primary_source = src if docs else "groq"
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
            question, db, lang,
            user_country=user_country, user_city=user_city,
        )
        result.retrieved_docs = docs
        result.primary_source = src
        return result

    # ------------------------------------------------------------------
    # Internal retrieval strategies
    # ------------------------------------------------------------------

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
            query=question, db=db,
            user_country=user_country,
            user_city=user_city,
            include_legal=True,
            language=language,
        )

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
                    question, db, top_k=per_collection_k,
                )
            elif coll_name == "nlp_knowledge":
                docs = await search_nlp_knowledge(
                    question, db, top_k=per_collection_k, language=language,
                )
            elif coll_name == "resources":
                docs = await search_resources(
                    question, db, top_k=per_collection_k,
                )
            elif coll_name == "legal_documents":
                docs = await search_legal_documents(
                    question, db, top_k=per_collection_k,
                )
            else:
                continue
            all_docs.extend(docs)

        all_docs.sort(key=lambda d: d.get("similarity", 0), reverse=True)
        top = all_docs[:top_k]
        primary = top[0]["source"] if top else "none"
        return top, primary


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_router: QueryRouter | None = None


def get_query_router() -> QueryRouter:
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router
