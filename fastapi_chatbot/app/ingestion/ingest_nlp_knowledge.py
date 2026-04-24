"""
Ingestion script for Arabic NLP knowledge base.

Persists structured data in PostgreSQL, embeddings in Qdrant.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_NLP_KNOWLEDGE
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NLP_KNOWLEDGE = [
    {
        "topic": "Arabic Stemming",
        "language": "en",
        "content": (
            "Stemming is the process of reducing Arabic words to their root form (stem).\n"
            "Arabic stemming is challenging due to:\n"
            "- Rich morphology with prefixes, suffixes, and infixes\n"
            "- Derivational and inflectional morphology\n"
            "- Agglutinative nature\n\n"
            "Common stemming algorithms:\n"
            "1. Light Stemming: Removes common prefixes/suffixes (Al-, -at, -un)\n"
            "2. Root-based Stemming: Extracts tri-literal/quad-literal roots\n"
            "3. Khoja Stemmer: Popular root-based stemmer\n"
            "4. ISRI Stemmer: Information Science Research Institute stemmer\n\n"
            "Applications:\n"
            "- Information retrieval\n"
            "- Text classification\n"
            "- Machine translation"
        ),
        "keywords": ["stemming", "morphology", "root", "Arabic"],
        "difficulty": "intermediate",
    },
    {
        "topic": "Named Entity Recognition (NER) for Arabic",
        "language": "en",
        "content": (
            "NER identifies and classifies named entities in Arabic text.\n\n"
            "Entity types: PERSON, LOCATION, ORGANIZATION, DATE, TIME, MONEY.\n\n"
            "Challenges for Arabic NER:\n"
            "- Lack of capitalization\n"
            "- Name ambiguity\n"
            "- Dialect variations\n"
            "- Limited annotated corpora\n\n"
            "Approaches:\n"
            "1. Rule-based: Gazetteers, patterns\n"
            "2. Machine Learning: CRF, SVM\n"
            "3. Deep Learning: BiLSTM-CRF, BERT (AraBERT, CAMeL BERT)\n\n"
            "Tools: CAMeL Tools, Stanford NER, spaCy with Arabic models"
        ),
        "keywords": ["NER", "entities", "Arabic", "BERT"],
        "difficulty": "advanced",
    },
    {
        "topic": "Arabic Diacritization",
        "language": "en",
        "content": (
            "Diacritization adds vowel marks (diacritics) to Arabic text.\n\n"
            "Arabic diacritics: Fatha, Damma, Kasra, Sukun, Shadda, Tanwin.\n\n"
            "Importance:\n"
            "- Resolves ambiguity\n"
            "- Essential for TTS and ASR\n"
            "- Helps learners\n"
            "- Improves machine translation\n\n"
            "Methods:\n"
            "1. Rule-based: Morphological analysis\n"
            "2. Statistical: HMM, CRF\n"
            "3. Neural: RNN, Transformer models\n\n"
            "State-of-the-art: Shakkala, Mishkal, Farasa"
        ),
        "keywords": ["diacritization", "tashkeel", "harakat", "vowels"],
        "difficulty": "intermediate",
    },
    {
        "topic": "Arabic Word Embeddings",
        "language": "en",
        "content": (
            "Word embeddings are dense vector representations of words.\n\n"
            "Types:\n"
            "1. Static: Word2Vec (Skip-gram, CBOW), GloVe, FastText\n"
            "2. Contextual: AraBERT, CAMeL BERT, AraGPT, mBERT\n\n"
            "Pretrained Arabic models: AraBERT v1/v2, CAMeL-BERT, AraELECTRA, MARBERT.\n\n"
            "Training corpora: Arabic Wikipedia, OSIAN, Arabic Gigaword, Common Crawl.\n\n"
            "Applications: Semantic similarity, text classification, machine translation, QA"
        ),
        "keywords": ["embeddings", "BERT", "word2vec", "vectors"],
        "difficulty": "advanced",
    },
]


async def ingest_nlp_knowledge():
    """Ingest NLP knowledge base into PostgreSQL + Qdrant."""
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        logger.info("Starting NLP knowledge ingestion...")
        points: list[PointStruct] = []

        for kd in NLP_KNOWLEDGE:
            text = f"{kd['topic']} {kd['content']}"
            embedding = embedding_service.encode_single(text)

            entry = NLPKnowledge(
                topic=kd["topic"],
                language=kd["language"],
                content=kd["content"],
                keywords=kd["keywords"],
                difficulty=kd["difficulty"],
            )
            db.add(entry)
            await db.flush()

            points.append(
                PointStruct(
                    id=entry.id,
                    vector=embedding,
                    payload={
                        "type": "nlp_knowledge",
                        "language": entry.language,
                        "difficulty": entry.difficulty or "",
                    },
                )
            )
            logger.info("Added: %s (id=%d)", entry.topic, entry.id)

        await db.commit()
        qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, points)
        logger.info("Ingested %d knowledge entries", len(NLP_KNOWLEDGE))


if __name__ == "__main__":
    asyncio.run(ingest_nlp_knowledge())
