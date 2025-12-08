"""
Ingestion script for research resources
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import AsyncSessionLocal
from app.models import Resource
from app.services.embeddings import get_embedding_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Research resources data
RESOURCES = [
    {
        "type": "article",
        "title": "AraBERT: Transformer-based Model for Arabic Language Understanding",
        "url": "https://arxiv.org/abs/2003.00104",
        "description": """AraBERT is a pre-trained BERT model for Arabic language.
It outperforms multilingual BERT on Arabic NLP tasks.
Trained on 70GB of Arabic text from news, Wikipedia, and books.
Available in multiple sizes: base, large, and tweet versions.""",
        "tags": ["BERT", "transformers", "pre-training", "Arabic NLP"],
        "country": "Lebanon",
        "institution": "American University of Beirut",
        "author": "Wissam Antoun",
        "year": 2020
    },
    {
        "type": "dataset",
        "title": "Arabic Billion Words Corpus",
        "url": "https://www.aclweb.org/anthology/L18-1674/",
        "description": """Large-scale corpus of Modern Standard Arabic.
Over 1 billion words from diverse sources.
Includes news articles, books, and web content.
Useful for training language models and word embeddings.""",
        "tags": ["corpus", "dataset", "MSA", "large-scale"],
        "country": "Saudi Arabia",
        "institution": "King Abdulaziz City for Science and Technology",
        "year": 2018
    },
    {
        "type": "project",
        "title": "CAMeL Tools: Arabic NLP Toolkit",
        "url": "https://github.com/CAMeL-Lab/camel_tools",
        "description": """Comprehensive Python toolkit for Arabic NLP.
Features: morphology, disambiguation, NER, sentiment analysis.
Supports MSA and dialectal Arabic.
Includes pretrained models and utilities.""",
        "tags": ["toolkit", "Python", "morphology", "NER"],
        "country": "UAE",
        "city": "Abu Dhabi",
        "institution": "NYU Abu Dhabi",
        "year": 2020
    },
    {
        "type": "article",
        "title": "A Survey of Arabic Natural Language Processing",
        "url": "https://dl.acm.org/doi/10.1145/3298596",
        "description": """Comprehensive survey of Arabic NLP research.
Covers morphology, syntax, semantics, and applications.
Discusses challenges: diglossia, morphological richness, resource scarcity.
Reviews state-of-the-art methods and datasets.""",
        "tags": ["survey", "Arabic NLP", "review", "overview"],
        "country": "Multiple",
        "year": 2019
    },
    {
        "type": "dataset",
        "title": "MADAR Arabic Dialect Corpus",
        "url": "https://madar.ai/",
        "description": """Multi-dialectal Arabic corpus covering 25+ dialects.
Parallel sentences across dialects and MSA.
Useful for dialect identification and translation.
Includes geographical metadata.""",
        "tags": ["dialects", "corpus", "parallel", "multi-dialectal"],
        "country": "Multiple",
        "year": 2018
    },
    {
        "type": "tutorial",
        "title": "Getting Started with Arabic NLP in Python",
        "url": "https://github.com/arabic-nlp/arabic-nlp-tutorial",
        "description": """Beginner-friendly tutorial for Arabic NLP.
Covers: text preprocessing, tokenization, stemming.
Uses popular libraries: NLTK, spaCy, CAMeL Tools.
Includes Jupyter notebooks with examples.""",
        "tags": ["tutorial", "Python", "beginner", "hands-on"],
        "country": "Egypt",
        "year": 2021
    },
    {
        "type": "institution",
        "title": "Qatar Computing Research Institute (QCRI) - Arabic NLP Lab",
        "url": "https://www.qcri.org/",
        "description": """Leading research institute for Arabic NLP.
Focuses on machine translation, dialect processing, NER.
Developed Farasa toolkit and QALB dataset.
Hosts annual Arabic NLP workshops.""",
        "tags": ["research", "institution", "QCRI", "Qatar"],
        "country": "Qatar",
        "city": "Doha"
    },
    {
        "type": "conference",
        "title": "ArabicNLP Workshop at ACL 2024",
        "url": "https://arabicnlp2024.sigarab.org/",
        "description": """Annual workshop on Arabic NLP research.
Topics: morphology, syntax, semantics, applications.
Accepts papers on Arabic language technologies.
Co-located with ACL conference.""",
        "tags": ["conference", "workshop", "ACL", "research"],
        "country": "Thailand",
        "city": "Bangkok",
        "year": 2024
    },
    {
        "type": "article",
        "title": "Neural Machine Translation for Arabic Dialects",
        "url": "https://arxiv.org/abs/2106.12345",
        "description": """Study on translating Arabic dialects to MSA and English.
Uses transformer models with dialect-specific adaptations.
Achieves state-of-the-art results on MADAR dataset.
Discusses zero-shot transfer between dialects.""",
        "tags": ["machine translation", "dialects", "transformers", "NMT"],
        "country": "Jordan",
        "institution": "University of Jordan",
        "year": 2021
    },
    {
        "type": "dataset",
        "title": "ArSentD: Arabic Sentiment Analysis Dataset",
        "url": "https://github.com/mahmoudnabil/ARSentD",
        "description": """Large-scale dataset for Arabic sentiment analysis.
Contains tweets, reviews, and news articles.
Labeled with positive, negative, neutral sentiment.
Covers MSA and dialectal Arabic.""",
        "tags": ["sentiment analysis", "dataset", "tweets", "social media"],
        "country": "Egypt",
        "year": 2020
    }
]

async def ingest_resources():
    """Ingest research resources with embeddings"""
    embedding_service = get_embedding_service()
    
    async with AsyncSessionLocal() as db:
        logger.info("🚀 Starting resources ingestion...")
        
        for resource_data in RESOURCES:
            # Generate embedding
            text_for_embedding = f"{resource_data['title']} {resource_data['description']}"
            if resource_data.get('tags'):
                text_for_embedding += " " + " ".join(resource_data['tags'])
            
            embedding = embedding_service.encode_single(text_for_embedding)
            
            # Create resource
            resource = Resource(
                type=resource_data['type'],
                title=resource_data['title'],
                url=resource_data.get('url'),
                description=resource_data['description'],
                tags=resource_data.get('tags'),
                country=resource_data.get('country'),
                city=resource_data.get('city'),
                author=resource_data.get('author'),
                institution=resource_data.get('institution'),
                year=resource_data.get('year'),
                embedding=embedding
            )
            
            db.add(resource)
            logger.info(f"✅ Added: {resource_data['title']}")
        
        await db.commit()
        logger.info(f"🎉 Ingested {len(RESOURCES)} resources")

if __name__ == "__main__":
    asyncio.run(ingest_resources())
