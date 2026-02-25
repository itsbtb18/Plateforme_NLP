"""
Qdrant collection names and payload schema constants.

Single source of truth for all collection identifiers and the
standardised payload fields each collection expects.
"""

# ---------------------------------------------------------------------------
# Collection names
# ---------------------------------------------------------------------------

COLLECTION_PLATFORM_DOCS = "platform_docs"
COLLECTION_NLP_KNOWLEDGE = "nlp_knowledge"
COLLECTION_RESOURCES = "resources"
COLLECTION_LEGAL_DOCUMENTS = "legal_documents"
COLLECTION_DOCUMENT_CHUNKS = "document_chunks"

ALL_COLLECTIONS = [
    COLLECTION_PLATFORM_DOCS,
    COLLECTION_NLP_KNOWLEDGE,
    COLLECTION_RESOURCES,
    COLLECTION_LEGAL_DOCUMENTS,
    COLLECTION_DOCUMENT_CHUNKS,
]

# ---------------------------------------------------------------------------
# Payload schema documentation (enforced by convention)
# ---------------------------------------------------------------------------
#
# Every Qdrant point MUST carry a payload with at least:
#   - type      (str)  — semantic category of the content
#   - language  (str)  — ISO 639-1 code (ar / en / fr)
#
# Per-collection payload fields:
#
# platform_docs:
#   type="nlp_knowledge", language, slug, category
#
# nlp_knowledge:
#   type="nlp_knowledge", language, difficulty
#
# resources:
#   type=<article|dataset|project|tutorial|…>, language, country, city
#
# legal_documents:
#   type="law", language, jurisdiction, category
#
# document_chunks:
#   type="document", language, owner_id, document_id, session_id,
#   filename, chunk_index, source="user_upload"
