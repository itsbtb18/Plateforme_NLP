from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PlatformDoc, NLPKnowledge, Resource
from app.services.embeddings import get_embedding_service
from app.config import get_settings
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class RetrievalService:
    """Service for retrieving relevant documents using vector similarity search"""
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.top_k = settings.TOP_K_RESULTS
        self.threshold = settings.SIMILARITY_THRESHOLD
    
    async def search_platform_docs(
        self,
        query: str,
        db: AsyncSession,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """Search platform documentation"""
        try:
            k = top_k or self.top_k
            query_embedding = self.embedding_service.encode_single(query)
            
            # Vector similarity search using <=> operator (cosine distance)
            stmt = select(
                PlatformDoc.id,
                PlatformDoc.title,
                PlatformDoc.content,
                PlatformDoc.slug,
                PlatformDoc.category,
                (1 - PlatformDoc.embedding.cosine_distance(query_embedding)).label('similarity')
            ).order_by(
                PlatformDoc.embedding.cosine_distance(query_embedding)
            ).limit(k)
            
            result = await db.execute(stmt)
            docs = result.all()
            
            return [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content,
                    "slug": doc.slug,
                    "category": doc.category,
                    "source": "platform_docs",
                    "similarity": float(doc.similarity)
                }
                for doc in docs
                if doc.similarity >= self.threshold
            ]
        except Exception as e:
            logger.warning(f"Error searching platform docs: {str(e)}")
            return []
    
    async def search_nlp_knowledge(
        self,
        query: str,
        db: AsyncSession,
        top_k: Optional[int] = None,
        language: Optional[str] = None
    ) -> List[Dict]:
        """Search NLP knowledge base"""
        try:
            k = top_k or self.top_k
            query_embedding = self.embedding_service.encode_single(query)
            
            stmt = select(
                NLPKnowledge.id,
                NLPKnowledge.topic,
                NLPKnowledge.content,
                NLPKnowledge.language,
                NLPKnowledge.keywords,
                NLPKnowledge.difficulty,
                (1 - NLPKnowledge.embedding.cosine_distance(query_embedding)).label('similarity')
            ).order_by(
                NLPKnowledge.embedding.cosine_distance(query_embedding)
            ).limit(k)
            
            # Filter by language if specified
            if language:
                stmt = stmt.where(NLPKnowledge.language == language)
            
            result = await db.execute(stmt)
            docs = result.all()
            
            return [
                {
                    "id": doc.id,
                    "title": doc.topic,
                    "content": doc.content,
                    "language": doc.language,
                    "keywords": doc.keywords,
                    "difficulty": doc.difficulty,
                    "source": "nlp_knowledge",
                    "similarity": float(doc.similarity)
                }
                for doc in docs
                if doc.similarity >= self.threshold
            ]
        except Exception as e:
            logger.warning(f"Error searching NLP knowledge: {str(e)}")
            return []
    
    async def search_resources(
        self,
        query: str,
        db: AsyncSession,
        top_k: Optional[int] = None,
        resource_type: Optional[str] = None,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None
    ) -> List[Dict]:
        """Search research resources"""
        try:
            k = top_k or self.top_k
            query_embedding = self.embedding_service.encode_single(query)
            
            stmt = select(
                Resource.id,
                Resource.type,
                Resource.title,
                Resource.description,
                Resource.url,
                Resource.tags,
                Resource.country,
                Resource.city,
                Resource.author,
                Resource.institution,
                Resource.year,
                (1 - Resource.embedding.cosine_distance(query_embedding)).label('similarity')
            ).order_by(
                Resource.embedding.cosine_distance(query_embedding)
            ).limit(k * 2)  # Get more to filter by location
            
            # Filter by resource type if specified
            if resource_type:
                stmt = stmt.where(Resource.type == resource_type)
            
            result = await db.execute(stmt)
            docs = result.all()
            
            # Post-process: boost local resources
            resources = []
            for doc in docs:
                if doc.similarity < self.threshold:
                    continue
                
                similarity = float(doc.similarity)
                
                # Boost score for location match
                if user_country and doc.country == user_country:
                    similarity += 0.1
                if user_city and doc.city == user_city:
                    similarity += 0.1
                
                resources.append({
                    "id": doc.id,
                    "type": doc.type,
                    "title": doc.title,
                    "content": doc.description,
                    "url": doc.url,
                    "tags": doc.tags,
                    "country": doc.country,
                    "city": doc.city,
                    "author": doc.author,
                    "institution": doc.institution,
                    "year": doc.year,
                    "source": "resources",
                    "similarity": min(similarity, 1.0)  # Cap at 1.0
                })
            
            # Re-sort and limit
            resources.sort(key=lambda x: x['similarity'], reverse=True)
            return resources[:k]
        except Exception as e:
            logger.warning(f"Error searching resources: {str(e)}")
            return []
    
    async def hybrid_search(
        self,
        query: str,
        db: AsyncSession,
        user_country: Optional[str] = None,
        user_city: Optional[str] = None
    ) -> Tuple[List[Dict], str]:
        """
        Perform intelligent hybrid search across all sources with weighted scoring
        Returns: (combined_results, primary_source)
        """
        try:
            # Search all sources with strategic top_k values
            platform_docs = await self.search_platform_docs(query, db, top_k=4)
            nlp_knowledge = await self.search_nlp_knowledge(query, db, top_k=4)
            resources = await self.search_resources(
                query, db, top_k=4,
                user_country=user_country,
                user_city=user_city
            )
            
            # Apply strategic weighting based on source relevance
            weighted_results = []
            
            # Platform docs get slight boost (users often ask about platform features)
            for doc in platform_docs:
                doc['weighted_score'] = doc['similarity'] * 1.1
                weighted_results.append(doc)
            
            # NLP knowledge gets standard weight
            for doc in nlp_knowledge:
                doc['weighted_score'] = doc['similarity'] * 1.0
                weighted_results.append(doc)
            
            # Resources get slight boost if local
            for doc in resources:
                boost = 1.0
                if user_country and doc.get('country') == user_country:
                    boost += 0.05
                if user_city and doc.get('city') == user_city:
                    boost += 0.05
                doc['weighted_score'] = doc['similarity'] * boost
                weighted_results.append(doc)
            
            if not weighted_results:
                logger.info(f"No results found for query: {query[:50]}...")
                return [], "none"
            
            # Sort by weighted score
            weighted_results.sort(key=lambda x: x['weighted_score'], reverse=True)
            
            # Determine primary source from top result
            primary_source = weighted_results[0]['source'] if weighted_results else "none"
            
            # Log search results for monitoring
            logger.info(f"✅ Hybrid search: {len(weighted_results)} results, primary: {primary_source}")
            
            # Return top K overall (remove weighted_score from output)
            top_results = weighted_results[:settings.TOP_K_RESULTS]
            for result in top_results:
                result.pop('weighted_score', None)
            
            return top_results, primary_source
            
        except Exception as e:
            logger.error(f"❌ Hybrid search error: {str(e)}")
            return [], "none"

# Singleton instance
_retrieval_service = None

def get_retrieval_service() -> RetrievalService:
    """Get or create retrieval service instance"""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service
