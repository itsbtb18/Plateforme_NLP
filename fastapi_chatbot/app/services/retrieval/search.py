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
        fetch_k = max(k * 4, 20)
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)
        qf = build_language_filter(language) if language else None

        # Cross-lingual first-class behavior:
        # fetch same-language and all-language candidates, then merge.
        strict_hits = qdrant.search(
            collection=COLLECTION_NLP_KNOWLEDGE,
            query_vector=qe,
            limit=fetch_k,
            query_filter=qf,
            score_threshold=0.30,
        ) if qf is not None else []

        broad_hits = qdrant.search(
            collection=COLLECTION_NLP_KNOWLEDGE,
            query_vector=qe,
            limit=fetch_k,
            query_filter=None,
            score_threshold=0.30,
        )

        merged: Dict[int, Dict] = {}
        for h in broad_hits:
            hid = int(h["id"])
            merged[hid] = h

        # Keep same-language preference, but never exclude cross-lingual docs.
        lang_bonus = 0.03
        for h in strict_hits:
            hid = int(h["id"])
            boosted = dict(h)
            boosted["score"] = min(float(h.get("score", 0.0)) + lang_bonus, 1.0)
            current = merged.get(hid)
            if current is None or boosted["score"] > float(current.get("score", 0.0)):
                merged[hid] = boosted

        hits = sorted(merged.values(), key=lambda x: float(x.get("score", 0.0)), reverse=True)[:fetch_k]
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
                    "document_type": getattr(r, "document_type", None),
                    "section_title": getattr(r, "section_title", None),
                    "source_file": getattr(r, "source_file", None),
                }
            )

        # Prefer file-backed records (ingested docs with source_file) over
        # legacy rows that have no source_file, then apply diversity.
        known = [r for r in results if r.get("source_file")]
        unknown = [r for r in results if not r.get("source_file")]
        if known and unknown:
            max_unknown = max(1, k // 4)
            unknown = unknown[:max_unknown]
        ranked = known + unknown

        # Keep result diversity across NLP source files so answers do not
        # collapse to chunks from only one or two documents.
        if len(ranked) <= k:
            return ranked

        from collections import defaultdict

        by_file: Dict[str, List[Dict]] = defaultdict(list)
        for row in ranked:
            key = row.get("source_file") or f"id-{row.get('id')}"
            by_file[key].append(row)

        selected: List[Dict] = []
        selected_ids = set()

        # Round 1: one best chunk per distinct source file.
        for key in by_file:
            cand = by_file[key][0]
            cid = cand.get("id")
            if cid not in selected_ids:
                selected.append(cand)
                selected_ids.add(cid)
            if len(selected) >= k:
                break

        # Round 2: fill remaining slots by global relevance.
        if len(selected) < k:
            for row in ranked:
                cid = row.get("id")
                if cid in selected_ids:
                    continue
                selected.append(row)
                selected_ids.add(cid)
                if len(selected) >= k:
                    break

        return selected[:k]
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
    """Search legal / regulatory knowledge base — cross-lingual.

    BGE-M3 maps Arabic, French, and English into the same vector space,
    so a query in Arabic will naturally match French legal documents.
    We intentionally do NOT filter by language — the embedding similarity
    handles cross-lingual matching.  Only jurisdiction and category
    filters are applied.

    The *language* parameter is kept in the signature for backward
    compatibility but is no longer used for filtering.
    """
    try:
        k = top_k or settings.TOP_K_RESULTS
        embedding_svc = get_embedding_service()
        qdrant = get_qdrant_service()

        qe = embedding_svc.encode_single(query)

        # Cross-lingual: search ALL languages, filter only by
        # jurisdiction/category.  BGE-M3 handles multilingual matching.
        base_filter = build_legal_filter(jurisdiction, category)
        hits = qdrant.search(
            collection=COLLECTION_LEGAL_DOCUMENTS,
            query_vector=qe,
            limit=k,
            query_filter=base_filter,
            score_threshold=0.40,
        )

        if not hits:
            return []

        # Extract real DB IDs from payload
        results_map = {}
        for h in hits:
            doc_id = h["payload"].get("doc_id")
            if doc_id is None:
                # Fallback to h["id"] if doc_id is missing (backward compat)
                doc_id = int(h["id"])
            
            if doc_id not in results_map:
                results_map[doc_id] = {
                    "score": h["score"],
                    "content": h["payload"].get("content", ""),
                    "article": h["payload"].get("article_heading"),
                }

        doc_ids = list(results_map.keys())
        stmt = select(LegalDocument).where(LegalDocument.id.in_(doc_ids))
        rows = (await db.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        results = []
        for doc_id, meta in results_map.items():
            r = row_map.get(doc_id)
            if not r:
                continue
            
            results.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "content": meta["content"],
                    "article_heading": meta["article"],
                    "similarity": meta["score"],
                    "source": "legal",
                    "language": r.language,
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
    document_ids: Optional[List[int]] = None,
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
        qf = build_user_doc_filter(session_id, owner_id, document_id, document_ids)

        logger.info(
            "search_user_documents: session=%s owner=%s doc_id=%s doc_ids=%s filter=%s",
            session_id,
            owner_id,
            document_id,
            document_ids,
            qf,
        )

        # When the user explicitly targets specific documents (upload-then-ask
        # flow), use a very low threshold so vague queries like "explain this"
        # still return chunks.  For open searches across all user docs, keep
        # the normal threshold to avoid noise.
        threshold = 0.05 if (document_ids or document_id) else 0.15

        # Retrieve more chunks than needed so we can balance across docs
        fetch_k = max(k * 3, 15)

        hits = qdrant.search(
            collection=COLLECTION_DOCUMENT_CHUNKS,
            query_vector=qe,
            limit=fetch_k,
            query_filter=qf,
            score_threshold=threshold,
        )
        logger.info("search_user_documents: %d hits returned", len(hits) if hits else 0)
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}
        payload_map = {h["id"]: h["payload"] for h in hits}

        # Phase 10: Named Entity Boost — extract entities from query,
        # boost chunks whose payload contains matching entities.
        from app.services.documents.entities import extract_entities, match_entities

        query_entities = extract_entities(query)
        ENTITY_BOOST = 0.06  # per matching entity

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

            # Apply entity boost
            if query_entities:
                chunk_entities = payload.get("entities", [])
                n_matches = match_entities(query_entities, chunk_entities)
                sim = min(sim + n_matches * ENTITY_BOOST, 1.0)

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
