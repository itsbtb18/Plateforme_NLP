"""
Ingestion script for platform documentation
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import AsyncSessionLocal
from app.models import PlatformDoc
from app.services.embeddings import get_embedding_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample platform documentation data
PLATFORM_DOCS = [
    {
        "slug": "getting-started",
        "title": "Getting Started with the Platform",
        "category": "features",
        "content": """Welcome to the Arabic NLP Research Platform. This platform provides:
- Collaborative research tools for Arabic NLP
- Access to datasets and resources
- Project management and sharing
- Community forums and discussions
- Chatbot assistant for help and guidance

To get started:
1. Create an account or log in
2. Complete your profile
3. Explore available resources
4. Join or create projects
5. Engage with the community"""
    },
    {
        "slug": "chatbot-usage",
        "title": "How to Use the Chatbot",
        "category": "features",
        "content": """The chatbot helps you with:
- Platform features and navigation
- Arabic NLP concepts and terminology
- Finding relevant research resources
- Troubleshooting common issues

Chatbot modes:
1. Conversation Mode: Ask follow-up questions with context
2. PDF Upload: Analyze research papers
3. Quick Question: Get fast answers
4. Resource Search: Find relevant articles and projects"""
    },
    {
        "slug": "project-management",
        "title": "Managing Research Projects",
        "category": "features",
        "content": """Create and manage Arabic NLP research projects:
- Create new projects with descriptions
- Add team members and collaborators
- Share resources and datasets
- Track progress and milestones
- Publish results and papers

Project types supported:
- Morphological analysis
- Named Entity Recognition
- Machine Translation
- Sentiment Analysis
- Text Classification"""
    },
    {
        "slug": "troubleshooting-login",
        "title": "Login and Authentication Issues",
        "category": "troubleshooting",
        "content": """Common login problems:
1. Forgot password: Use the 'Forgot Password' link
2. Email not verified: Check your inbox for verification email
3. Account locked: Contact support after 5 failed attempts
4. Session expired: Log in again

If issues persist, contact: support@arabicnlp-platform.com"""
    },
    {
        "slug": "resource-library",
        "title": "Using the Resource Library",
        "category": "features",
        "content": """Access Arabic NLP resources:
- Research papers and publications
- Datasets (corpora, lexicons, annotations)
- Tools and software packages
- Tutorials and documentation
- Conference proceedings

Filter by:
- Resource type
- Language (Arabic dialects)
- Domain (news, social media, literature)
- Country and institution"""
    }
]

async def ingest_platform_docs():
    """Ingest platform documentation with embeddings"""
    embedding_service = get_embedding_service()
    
    async with AsyncSessionLocal() as db:
        logger.info("🚀 Starting platform docs ingestion...")
        
        for doc_data in PLATFORM_DOCS:
            # Generate embedding
            text_for_embedding = f"{doc_data['title']} {doc_data['content']}"
            embedding = embedding_service.encode_single(text_for_embedding)
            
            # Create document
            doc = PlatformDoc(
                slug=doc_data['slug'],
                title=doc_data['title'],
                category=doc_data['category'],
                content=doc_data['content'],
                embedding=embedding
            )
            
            db.add(doc)
            logger.info(f"✅ Added: {doc_data['title']}")
        
        await db.commit()
        logger.info(f"🎉 Ingested {len(PLATFORM_DOCS)} platform documents")

if __name__ == "__main__":
    asyncio.run(ingest_platform_docs())
