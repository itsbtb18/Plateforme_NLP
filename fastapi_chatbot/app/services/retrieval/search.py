"""
Per-source search methods — one function per Qdrant collection.

Each function:
  1. Encodes the query
  2. Calls Qdrant with optional filters
  3. Enriches results from PostgreSQL
  4. Returns a list of dicts ready for hybrid merge
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
import logging

from app.models import (
    PlatformDoc,
    NLPKnowledge,
    Resource,
    LegalDocument,
    DocumentChunk,
)
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import (
    get_qdrant_service,
    COLLECTION_PLATFORM_DOCS,
    COLLECTION_NLP_KNOWLEDGE,
    COLLECTION_RESOURCES,
    COLLECTION_LEGAL_DOCUMENTS,
    COLLECTION_DOCUMENT_CHUNKS,
)
from app.services.retrieval.filters import (
    build_language_filter,
    build_legal_filter,
    build_resource_filter,
    build_user_doc_filter,
)
from app.config import get_settings
from qdrant_client.models import Filter

logger = logging.getLogger(__name__)
settings = get_settings()


async def search_platform_docs(
    query: str,
    db: AsyncSession,
    top_k: Optional[int] = None,
) -> List[Dict]:
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)
        hits = qdrant.search(
            collection=COLLECTION_PLATFORM_DOCS,
            query_vector=qe,
            limit=k,
        )
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}

        stmt = select(PlatformDoc).where(PlatformDoc.id.in_(ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        results = []
        for pid in ids:
            r = row_map.get(pid)
            if not r:
                continue
            results.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content,
                    "slug": r.slug,
                    "category": r.category,
                    "source": "platform_docs",
                    "similarity": score_map[pid],
                }
            )
        return results
    except Exception as e:
        logger.error("Platform docs search error: %s", e, exc_info=True)
        return []


async def search_nlp_knowledge(
    query: str,
    db: AsyncSession,
    top_k: Optional[int] = None,
    language: Optional[str] = None,
) -> List[Dict]:
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)
        qf = build_language_filter(language) if language else None

        hits = qdrant.search(
            collection=COLLECTION_NLP_KNOWLEDGE,
            query_vector=qe,
            limit=k,
            query_filter=qf,
        )
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}

        stmt = select(NLPKnowledge).where(NLPKnowledge.id.in_(ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        results = []
        for pid in ids:
            r = row_map.get(pid)
            if not r:
                continue
            results.append(
                {
                    "id": r.id,
                    "title": r.topic,
                    "content": r.content,
                    "language": r.language,
                    "keywords": r.keywords,
                    "difficulty": r.difficulty,
                    "source": "nlp_knowledge",
                    "similarity": score_map[pid],
                }
            )
        return results
    except Exception as e:
        logger.error("NLP knowledge search error: %s", e, exc_info=True)
        return []


async def search_resources(
    query: str,
    db: AsyncSession,
    top_k: Optional[int] = None,
    resource_type: Optional[str] = None,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
) -> List[Dict]:
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)
        qf = build_resource_filter(resource_type)

        hits = qdrant.search(
            collection=COLLECTION_RESOURCES,
            query_vector=qe,
            limit=k * 2,
            query_filter=qf,
        )
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}

        stmt = select(Resource).where(Resource.id.in_(ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        results = []
        for pid in ids:
            r = row_map.get(pid)
            if not r:
                continue
            sim = score_map[pid]
            if user_country and r.country == user_country:
                sim = min(sim + 0.1, 1.0)
            if user_city and r.city == user_city:
                sim = min(sim + 0.1, 1.0)
            results.append(
                {
                    "id": r.id,
                    "type": r.type,
                    "title": r.title,
                    "content": r.description,
                    "url": r.url,
                    "tags": r.tags,
                    "country": r.country,
                    "city": r.city,
                    "author": r.author,
                    "institution": r.institution,
                    "year": r.year,
                    "source": "resources",
                    "similarity": sim,
                }
            )
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:k]
    except Exception as e:
        logger.error("Resources search error: %s", e, exc_info=True)
        return []


async def search_legal_documents(
    query: str,
    db: AsyncSession,
    top_k: Optional[int] = None,
    jurisdiction: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict]:
    """Search legal / regulatory knowledge base.

    When *language* is provided, same-language documents are prioritised
    by first searching with language filter.  If too few results,
    a cross-language fallback is performed.
    """
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)

        # Phase 6: prioritise same-language laws
        if language:
            lang_filter = build_legal_filter(jurisdiction, category, language)
            lang_hits = qdrant.search(
                collection=COLLECTION_LEGAL_DOCUMENTS,
                query_vector=qe,
                limit=k,
                query_filter=lang_filter,
            )
            if len(lang_hits) >= max(1, k // 2):
                hits = lang_hits
            else:
                # Not enough same-language results — fall back to all languages
                base_filter = build_legal_filter(jurisdiction, category)
                all_hits = qdrant.search(
                    collection=COLLECTION_LEGAL_DOCUMENTS,
                    query_vector=qe,
                    limit=k,
                    query_filter=base_filter,
                )
                # Merge: same-language first, then cross-language
                seen_ids = {h["id"] for h in lang_hits}
                hits = lang_hits + [h for h in all_hits if h["id"] not in seen_ids]
                hits = hits[:k]
        else:
            base_filter = build_legal_filter(jurisdiction, category)
            hits = qdrant.search(
                collection=COLLECTION_LEGAL_DOCUMENTS,
                query_vector=qe,
                limit=k,
                query_filter=base_filter,
            )

        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}

        stmt = select(LegalDocument).where(LegalDocument.id.in_(ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        results = []
        for pid in ids:
            r = row_map.get(pid)
            if not r:
                continue
            sim = score_map[pid]
            # Qdrant server-side score_threshold already filters low-quality
            # results — no need to double-filter here.
            results.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content,
                    "jurisdiction": r.jurisdiction,
                    "category": r.category,
                    "language": r.language,
                    "source_reference": r.source_reference,
                    "keywords": r.keywords,
                    "source": "legal",
                    "similarity": sim,
                }
            )
        return results
    except Exception as e:
        logger.error("Legal docs search error: %s", e, exc_info=True)
        return []


async def search_user_documents(
    query: str,
    db: AsyncSession,
    session_id: Optional[str] = None,
    document_id: Optional[int] = None,
    top_k: Optional[int] = None,
    owner_id: Optional[str] = None,
) -> List[Dict]:
    """Search chunks of user-uploaded documents via Qdrant.

    Phase 6: when *owner_id* is provided, chunks are filtered
    so only the document owner's uploads are searched.

    Phase 12: balanced retrieval — ensures at least 2 chunks per
    unique document so multi-doc queries ("summarise those documents")
    cover ALL uploaded files, not just the highest-scoring one.
    """
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)
        qf = build_user_doc_filter(session_id, owner_id, document_id)

        # Retrieve more chunks than needed so we can balance across docs
        fetch_k = max(k * 3, 15)

        hits = qdrant.search(
            collection=COLLECTION_DOCUMENT_CHUNKS,
            query_vector=qe,
            limit=fetch_k,
            query_filter=qf,
            score_threshold=0.15,
        )
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}
        payload_map = {h["id"]: h["payload"] for h in hits}

        stmt = select(DocumentChunk).where(DocumentChunk.id.in_(ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        # Build raw results sorted by similarity (descending)
        raw_results = []
        for pid in ids:
            r = row_map.get(pid)
            payload = payload_map.get(pid, {})
            if not r:
                continue
            sim = score_map[pid]
            raw_results.append(
                {
                    "id": r.id,
                    "title": payload.get("filename", ""),
                    "content": r.content,
                    "page": r.page_number,
                    "document_id": r.document_id,
                    "source": "user_document",
                    "similarity": sim,
                }
            )

        if not raw_results:
            return []

        # --- Balanced selection across documents ---
        # Group by filename (deduplicates re-uploaded files automatically)
        from collections import defaultdict

        by_file: Dict[str, List[Dict]] = defaultdict(list)
        for r in raw_results:
            by_file[r["title"]].append(r)

        unique_files = list(by_file.keys())
        if len(unique_files) <= 1:
            # Only one document — return top k as-is
            return raw_results[:k]

        # Guarantee at least MIN_PER_DOC chunks per document
        MIN_PER_DOC = 2
        selected: List[Dict] = []
        selected_ids = set()

        # Round 1: pick top MIN_PER_DOC from each document
        for fname in unique_files:
            for chunk in by_file[fname][:MIN_PER_DOC]:
                if chunk["id"] not in selected_ids:
                    selected.append(chunk)
                    selected_ids.add(chunk["id"])

        # Round 2: fill remaining slots with highest-scoring chunks
        remaining = k - len(selected)
        if remaining > 0:
            for r in raw_results:
                if r["id"] not in selected_ids:
                    selected.append(r)
                    selected_ids.add(r["id"])
                    remaining -= 1
                    if remaining <= 0:
                        break

        # Sort final selection by similarity descending
        selected.sort(key=lambda x: x["similarity"], reverse=True)
        return selected[:k]
    except Exception as e:
        logger.error("User documents search error: %s", e, exc_info=True)
        return []
