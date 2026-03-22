import asyncio

from qdrant_client.models import PointStruct

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import COLLECTION_NLP_KNOWLEDGE, get_qdrant_service

RAG_TEXT = (
    "RAG stands for Retrieval-Augmented Generation. "
    "It combines a retriever that fetches relevant passages from a knowledge base "
    "with a generator that produces answers grounded in those retrieved passages. "
    "Main flow: query encoding, document retrieval, context construction, LLM generation, and optional faithfulness checking. "
    "Benefits: better factuality, reduced hallucination risk, and domain grounding. "
    "Agentic RAG extends RAG by adding planning/tool-use loops where an agent can reformulate queries, call multiple tools, verify evidence, and iterate before final answer."
)


async def main():
    embedding = get_embedding_service().encode_single(
        "RAG Retrieval Augmented Generation " + RAG_TEXT
    )
    qdrant = get_qdrant_service()

    async with AsyncSessionLocal() as db:
        entry = NLPKnowledge(
            topic="RAG and Agentic RAG",
            language="en",
            content=RAG_TEXT,
            keywords=["rag", "retrieval", "agentic rag", "hallucination"],
            difficulty="intermediate",
            source_file="manual_seed_rag",
            section_title="RAG and Agentic RAG",
            document_type="tutorial",
            version=2,
        )
        db.add(entry)
        await db.flush()

        point = PointStruct(
            id=entry.id,
            vector=embedding,
            payload={
                "type": "nlp_knowledge",
                "language": "en",
                "difficulty": "intermediate",
                "source_file": "manual_seed_rag",
                "document_type": "tutorial",
                "section_title": "RAG and Agentic RAG",
                "content": RAG_TEXT[:1000],
                "title": "RAG and Agentic RAG",
                "version": 2,
            },
        )

        await db.commit()
        qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, [point])
        print("inserted_id", entry.id)


if __name__ == "__main__":
    asyncio.run(main())
