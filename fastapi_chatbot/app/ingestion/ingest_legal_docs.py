"""
Ingestion script for legal / regulatory knowledge base.

Persists structured data in PostgreSQL, embeddings in Qdrant.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import LegalDocument
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_LEGAL_DOCUMENTS
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LEGAL_DOCUMENTS = [
    {
        "title": "GDPR and Arabic NLP Research",
        "jurisdiction": "EU",
        "category": "data-protection",
        "language": "en",
        "content": (
            "The General Data Protection Regulation (GDPR) applies to any processing of "
            "personal data of EU residents, including NLP datasets that contain personal "
            "information.\n\n"
            "Key implications for NLP researchers:\n"
            "- Consent: explicit consent required for personal data in training corpora\n"
            "- Right to erasure: individuals can request deletion of their data\n"
            "- Data minimisation: collect only data necessary for the research purpose\n"
            "- Pseudonymisation: recommended for text corpora containing names\n"
            "- Cross-border transfers: special rules for data leaving the EU"
        ),
        "keywords": ["GDPR", "data protection", "personal data", "consent", "NLP datasets"],
        "source_reference": "Regulation (EU) 2016/679",
    },
    {
        "title": "EU AI Act -- Implications for NLP Systems",
        "jurisdiction": "EU",
        "category": "AI-regulation",
        "language": "en",
        "content": (
            "The EU AI Act classifies AI systems by risk level.\n\n"
            "Risk categories relevant to NLP:\n"
            "- High risk: systems used in employment, education, law enforcement\n"
            "- Limited risk: chatbots (transparency obligations)\n"
            "- Minimal risk: most research tools\n\n"
            "Requirements for NLP chatbots:\n"
            "1. Disclose that users are interacting with an AI system\n"
            "2. Ensure human oversight mechanisms\n"
            "3. Document training data provenance"
        ),
        "keywords": ["EU AI Act", "AI regulation", "risk classification", "chatbot"],
        "source_reference": "Regulation (EU) 2024/1689",
    },
    {
        "title": "Copyright and NLP Training Data",
        "jurisdiction": "International",
        "category": "intellectual-property",
        "language": "en",
        "content": (
            "Copyright considerations for NLP training data:\n\n"
            "Key issues:\n"
            "1. Web scraping: reproducing copyrighted text may infringe copyright\n"
            "2. Fair use / fair dealing: varies by jurisdiction\n"
            "3. Text and Data Mining (TDM) exceptions\n\n"
            "Best practices for researchers:\n"
            "- Prefer openly licensed corpora (CC-BY, CC0)\n"
            "- Document data provenance and licensing terms\n"
            "- Consider opt-out mechanisms for rights holders"
        ),
        "keywords": ["copyright", "training data", "fair use", "text mining", "TDM"],
        "source_reference": "Directive (EU) 2019/790 (DSM Directive), US Copyright Act",
    },
    {
        "title": "Ethical Guidelines for Arabic NLP Research",
        "jurisdiction": "International",
        "category": "ethics",
        "language": "en",
        "content": (
            "Ethical considerations specific to Arabic NLP:\n\n"
            "1. Bias and fairness:\n"
            "   - Dialectal bias: models trained on MSA may underperform on dialects\n"
            "   - Gender bias: Arabic grammatical gender can amplify stereotypes\n\n"
            "2. Cultural sensitivity:\n"
            "   - Religious content requires respectful handling\n\n"
            "3. Transparency:\n"
            "   - Document model limitations for Arabic\n"
            "   - Publish model cards in Arabic and English"
        ),
        "keywords": ["ethics", "bias", "fairness", "Arabic NLP", "cultural sensitivity"],
        "source_reference": "ACL Ethics Policy, UNESCO AI Ethics Recommendation",
    },
]


async def ingest_legal_documents():
    """Ingest legal knowledge base into PostgreSQL + Qdrant."""
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        logger.info("Starting legal documents ingestion...")
        points: list[PointStruct] = []

        for doc_data in LEGAL_DOCUMENTS:
            text = f"{doc_data['title']} {doc_data['content']}"
            embedding = embedding_service.encode_single(text)

            legal_doc = LegalDocument(
                title=doc_data["title"],
                jurisdiction=doc_data.get("jurisdiction"),
                category=doc_data.get("category"),
                content=doc_data["content"],
                language=doc_data.get("language", "en"),
                source_reference=doc_data.get("source_reference"),
                keywords=doc_data.get("keywords"),
            )
            db.add(legal_doc)
            await db.flush()

            points.append(
                PointStruct(
                    id=legal_doc.id,
                    vector=embedding,
                    payload={
                        "type": "law",
                        "language": legal_doc.language or "en",
                        "jurisdiction": legal_doc.jurisdiction or "",
                        "category": legal_doc.category or "",
                    },
                )
            )
            logger.info("Added: %s (id=%d)", doc_data["title"], legal_doc.id)

        await db.commit()
        qdrant.upsert_batch(COLLECTION_LEGAL_DOCUMENTS, points)
        logger.info("Ingested %d legal documents", len(LEGAL_DOCUMENTS))


if __name__ == "__main__":
    asyncio.run(ingest_legal_documents())
