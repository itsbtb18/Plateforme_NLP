"""
Ingestion script for research resources.

Persists structured data in PostgreSQL, embeddings in Qdrant.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import Resource
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_RESOURCES
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESOURCES = [
    {
        "type": "article",
        "title": "AraBERT: Transformer-based Model for Arabic Language Understanding",
        "url": "https://arxiv.org/abs/2003.00104",
        "description": (
            "AraBERT is a pre-trained BERT model for Arabic language. "
            "It outperforms multilingual BERT on Arabic NLP tasks. "
            "Trained on 70GB of Arabic text from news, Wikipedia, and books."
        ),
        "tags": ["BERT", "transformers", "pre-training", "Arabic NLP"],
        "country": "Lebanon",
        "institution": "American University of Beirut",
        "author": "Wissam Antoun",
        "year": 2020,
    },
    {
        "type": "dataset",
        "title": "Arabic Billion Words Corpus",
        "url": "https://www.aclweb.org/anthology/L18-1674/",
        "description": (
            "Large-scale corpus of Modern Standard Arabic. "
            "Over 1 billion words from diverse sources."
        ),
        "tags": ["corpus", "dataset", "MSA", "large-scale"],
        "country": "Saudi Arabia",
        "institution": "King Abdulaziz City for Science and Technology",
        "year": 2018,
    },
    {
        "type": "project",
        "title": "CAMeL Tools: Arabic NLP Toolkit",
        "url": "https://github.com/CAMeL-Lab/camel_tools",
        "description": (
            "Comprehensive Python toolkit for Arabic NLP. "
            "Features: morphology, disambiguation, NER, sentiment analysis."
        ),
        "tags": ["toolkit", "Python", "morphology", "NER"],
        "country": "UAE",
        "city": "Abu Dhabi",
        "institution": "NYU Abu Dhabi",
        "year": 2020,
    },
    {
        "type": "tutorial",
        "title": "Getting Started with Arabic NLP in Python",
        "url": "https://github.com/arabic-nlp/arabic-nlp-tutorial",
        "description": (
            "Beginner-friendly tutorial for Arabic NLP. "
            "Covers: text preprocessing, tokenization, stemming."
        ),
        "tags": ["tutorial", "Python", "beginner", "hands-on"],
        "country": "Egypt",
        "year": 2021,
    },
]


async def ingest_resources():
    """Ingest research resources into PostgreSQL + Qdrant."""
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        logger.info("Starting resources ingestion...")
        points: list[PointStruct] = []

        for rd in RESOURCES:
            text = f"{rd['title']} {rd['description']}"
            embedding = embedding_service.encode_single(text)

            res = Resource(
                type=rd["type"],
                title=rd["title"],
                url=rd.get("url"),
                description=rd["description"],
                tags=rd.get("tags"),
                country=rd.get("country"),
                city=rd.get("city"),
                author=rd.get("author"),
                institution=rd.get("institution"),
                year=rd.get("year"),
            )
            db.add(res)
            await db.flush()

            points.append(
                PointStruct(
                    id=res.id,
                    vector=embedding,
                    payload={
                        "type": res.type,
                        "language": "en",
                        "country": res.country or "",
                        "city": res.city or "",
                    },
                )
            )
            logger.info("Added: %s (id=%d)", res.title, res.id)

        await db.commit()
        qdrant.upsert_batch(COLLECTION_RESOURCES, points)
        logger.info("Ingested %d resources", len(RESOURCES))


if __name__ == "__main__":
    asyncio.run(ingest_resources())
