"""
Ingestion script for platform documentation.

Persists structured data in PostgreSQL, embeddings in Qdrant.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import PlatformDoc
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_PLATFORM_DOCS
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLATFORM_DOCS = [
    {
        "slug": "getting-started",
        "title": "Getting Started with the Platform",
        "category": "features",
        "content": (
            "Welcome to the Arabic NLP Research Platform. This platform provides:\n"
            "- Collaborative research tools for Arabic NLP\n"
            "- Access to datasets and resources\n"
            "- Project management and sharing\n"
            "- Community forums and discussions\n"
            "- Chatbot assistant for help and guidance\n\n"
            "To get started:\n"
            "1. Create an account or log in\n"
            "2. Complete your profile\n"
            "3. Explore available resources\n"
            "4. Join or create projects\n"
            "5. Engage with the community"
        ),
    },
    {
        "slug": "chatbot-usage",
        "title": "How to Use the Chatbot",
        "category": "features",
        "content": (
            "The chatbot helps you with:\n"
            "- Platform features and navigation\n"
            "- Arabic NLP concepts and terminology\n"
            "- Finding relevant research resources\n"
            "- Troubleshooting common issues\n\n"
            "Chatbot modes:\n"
            "1. Conversation Mode: Ask follow-up questions with context\n"
            "2. PDF Upload: Analyze research papers\n"
            "3. Quick Question: Get fast answers\n"
            "4. Resource Search: Find relevant articles and projects"
        ),
    },
    {
        "slug": "project-management",
        "title": "Managing Research Projects",
        "category": "features",
        "content": (
            "Create and manage Arabic NLP research projects:\n"
            "- Create new projects with descriptions\n"
            "- Add team members and collaborators\n"
            "- Share resources and datasets\n"
            "- Track progress and milestones\n"
            "- Publish results and papers\n\n"
            "Project types supported:\n"
            "- Morphological analysis\n"
            "- Named Entity Recognition\n"
            "- Machine Translation\n"
            "- Sentiment Analysis\n"
            "- Text Classification"
        ),
    },
    {
        "slug": "troubleshooting-login",
        "title": "Login and Authentication Issues",
        "category": "troubleshooting",
        "content": (
            "Common login problems:\n"
            "1. Forgot password: Use the Forgot Password link\n"
            "2. Email not verified: Check your inbox for verification email\n"
            "3. Account locked: Contact support after 5 failed attempts\n"
            "4. Session expired: Log in again\n\n"
            "If issues persist, contact: support@arabicnlp-platform.com"
        ),
    },
    {
        "slug": "resource-library",
        "title": "Using the Resource Library",
        "category": "features",
        "content": (
            "Access Arabic NLP resources:\n"
            "- Research papers and publications\n"
            "- Datasets (corpora, lexicons, annotations)\n"
            "- Tools and software packages\n"
            "- Tutorials and documentation\n"
            "- Conference proceedings\n\n"
            "Filter by:\n"
            "- Resource type\n"
            "- Language (Arabic dialects)\n"
            "- Domain (news, social media, literature)\n"
            "- Country and institution"
        ),
    },
]


async def ingest_platform_docs():
    """Ingest platform documentation into PostgreSQL + Qdrant."""
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        logger.info("Starting platform docs ingestion...")
        points: list[PointStruct] = []

        for doc_data in PLATFORM_DOCS:
            text = f"{doc_data['title']} {doc_data['content']}"
            embedding = embedding_service.encode_single(text)

            doc = PlatformDoc(
                slug=doc_data["slug"],
                title=doc_data["title"],
                category=doc_data["category"],
                content=doc_data["content"],
            )
            db.add(doc)
            await db.flush()

            points.append(
                PointStruct(
                    id=doc.id,
                    vector=embedding,
                    payload={
                        "type": "nlp_knowledge",
                        "language": "en",
                        "slug": doc.slug,
                        "category": doc.category or "",
                    },
                )
            )
            logger.info("Added: %s (id=%d)", doc.title, doc.id)

        await db.commit()
        qdrant.upsert_batch(COLLECTION_PLATFORM_DOCS, points)
        logger.info("Ingested %d platform documents", len(PLATFORM_DOCS))


if __name__ == "__main__":
    asyncio.run(ingest_platform_docs())
