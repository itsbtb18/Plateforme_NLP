"""
BM25 sparse retrieval module — Phase 4.

Provides term-based (sparse) retrieval to complement Qdrant's dense
vector search.  Results are fused with dense results using Reciprocal
Rank Fusion (RRF) in hybrid.py.

The BM25 index is lazily built from Qdrant collection payloads on first
query.  For large corpora this could be moved to Elasticsearch, but for
the current data scale an in-memory BM25 index is efficient.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokeniser — simple multilingual word splitter
# ---------------------------------------------------------------------------

# Arabic stop words (most common)
_AR_STOPWORDS = {
    "في", "من", "على", "إلى", "عن", "مع", "هو", "هي", "هذا", "هذه",
    "ذلك", "تلك", "التي", "الذي", "التي", "أن", "إن", "كان", "كانت",
    "ما", "لا", "لم", "لن", "قد", "و", "أو", "ثم", "بل", "لكن",
}

# French stop words
_FR_STOPWORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en",
    "est", "que", "qui", "dans", "pour", "par", "sur", "au", "aux",
    "ce", "ces", "son", "sa", "ses", "il", "elle", "nous", "vous",
    "leur", "ne", "pas", "plus", "ou", "mais", "avec",
}

# English stop words
_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "because", "but", "and", "or",
    "if", "while", "this", "that", "these", "those", "it", "its",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "they", "them", "their", "theirs",
}

_ALL_STOPWORDS = _AR_STOPWORDS | _FR_STOPWORDS | _EN_STOPWORDS

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    """Simple multilingual tokeniser with stop-word removal."""
    words = _WORD_RE.findall(text.lower())
    return [w for w in words if w not in _ALL_STOPWORDS and len(w) > 1]


# ---------------------------------------------------------------------------
# BM25 Index
# ---------------------------------------------------------------------------

class BM25Index:
    """In-memory BM25 index over a list of documents.

    Each document is a dict with at least a "content" key.
    The index preserves references to the original dicts so retrieval
    returns the full document metadata.
    """

    def __init__(self):
        self._docs: List[Dict] = []
        self._tokenized: List[List[str]] = []
        self._bm25 = None
        self._ready = False

    def build(self, documents: List[Dict]) -> None:
        """Build (or rebuild) the BM25 index from documents."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.error(
                "rank-bm25 not installed. Run: pip install rank-bm25"
            )
            return

        self._docs = documents
        self._tokenized = [
            tokenize(doc.get("content", "")) for doc in documents
        ]
        self._bm25 = BM25Okapi(self._tokenized)
        self._ready = True
        logger.info("BM25 index built: %d documents", len(documents))

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[Dict, float]]:
        """Search the BM25 index.

        Returns list of (document_dict, bm25_score) tuples sorted by
        descending score.
        """
        if not self._ready or self._bm25 is None:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        # Get top-k indices by score
        scored_indices = [
            (i, float(scores[i]))
            for i in range(len(scores))
            if scores[i] > 0
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scored_indices[:top_k]:
            results.append((self._docs[idx], score))

        return results

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def doc_count(self) -> int:
        return len(self._docs)


# ---------------------------------------------------------------------------
# Collection-specific indices
# ---------------------------------------------------------------------------

# Lazy singleton indices per collection
_indices: Dict[str, BM25Index] = {}


def get_bm25_index(collection: str) -> BM25Index:
    """Get or create a BM25 index for a specific collection.

    The index is lazily initialised — call build() to populate it.
    """
    if collection not in _indices:
        _indices[collection] = BM25Index()
    return _indices[collection]


def build_index_from_docs(
    collection: str,
    documents: List[Dict],
) -> BM25Index:
    """Build a BM25 index for a collection from a list of documents."""
    index = get_bm25_index(collection)
    index.build(documents)
    return index


def search_bm25(
    query: str,
    collection: str,
    top_k: int = 10,
) -> List[Dict]:
    """Search BM25 index for a collection.

    Returns documents enriched with a 'bm25_score' field.
    If the index isn't built yet, returns empty list.
    """
    index = get_bm25_index(collection)
    if not index.is_ready:
        logger.debug(
            "BM25 index not ready for collection '%s', skipping sparse search",
            collection,
        )
        return []

    results = index.search(query, top_k=top_k)
    out = []
    for doc, score in results:
        enriched = dict(doc)
        enriched["bm25_score"] = score
        out.append(enriched)

    return out


def build_from_qdrant(collection: str) -> bool:
    """Scroll a Qdrant collection and build the BM25 index from payloads.

    Payloads must have a 'content' field (stored during ingestion).
    Falls back to 'title' if 'content' is missing.

    Returns True if index was built successfully, False otherwise.
    """
    try:
        from app.services.qdrant import get_qdrant_service

        qdrant = get_qdrant_service()
        client = qdrant.client

        # Get total points count first
        info = client.get_collection(collection)
        total = info.points_count or 0
        if total == 0:
            logger.info("BM25: collection '%s' is empty, skipping", collection)
            return False

        # Scroll all payloads (no vectors needed)
        documents: List[Dict] = []
        offset = None
        batch_size = 100

        while True:
            scroll_result = client.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            points, next_offset = scroll_result

            for point in points:
                payload = point.payload or {}
                content = payload.get("content", "") or payload.get("title", "")
                if content:
                    doc = dict(payload)
                    doc["id"] = point.id
                    doc["content"] = content
                    documents.append(doc)

            if next_offset is None:
                break
            offset = next_offset

        if not documents:
            logger.info(
                "BM25: collection '%s' has %d points but no content payloads",
                collection, total,
            )
            return False

        build_index_from_docs(collection, documents)
        logger.info(
            "BM25: built index for '%s' — %d documents",
            collection, len(documents),
        )
        return True

    except Exception as e:
        logger.warning("BM25: failed to build index for '%s': %s", collection, e)
        return False
