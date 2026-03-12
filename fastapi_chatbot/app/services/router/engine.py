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
        user_email: Optional[str] = None,
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
            result.skip_retrieval = True
            result.primary_source = "groq"
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

            if not docs:
                result.skip_retrieval = True
                result.primary_source = "groq"
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
                language=lang,
            )
            result.retrieved_docs = docs
            result.primary_source = "legal" if docs else "none"
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
                result.primary_source = "groq"
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
        "legal_documents": 0.60,
        "nlp_knowledge": 0.55,
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


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_router: QueryRouter | None = None


def get_query_router() -> QueryRouter:
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router
