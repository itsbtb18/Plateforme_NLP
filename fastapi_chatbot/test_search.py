"""Test vector search scores for document 9."""


def main() -> None:
    from app.services.documents.embeddings import get_embedding_service
    from app.services.qdrant import get_qdrant_service
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

    emb = get_embedding_service()
    qdrant = get_qdrant_service()

    owner = "7a58de67-1a32-4a42-8cbf-aba937365904"
    doc_id = 9

    qf = Filter(
        must=[
            FieldCondition(key="owner_id", match=MatchValue(value=owner)),
            FieldCondition(key="document_id", match=MatchAny(any=[doc_id])),
        ]
    )

    for query in [
        "explain this also",
        "explain this for me",
        "what is this document about",
        "platform report",
    ]:
        qe = emb.encode_single(query)
        hits = qdrant.client.search(
            collection_name="document_chunks",
            query_vector=qe,
            limit=5,
            query_filter=qf,
            score_threshold=None,
        )
        print("Query: '%s' -> %d hits" % (query, len(hits)))
        for h in hits[:3]:
            ci = h.payload.get("chunk_index")
            print("  id=%d score=%.4f chunk=%s" % (h.id, h.score, ci))

        hits2 = qdrant.client.search(
            collection_name="document_chunks",
            query_vector=qe,
            limit=5,
            query_filter=qf,
            score_threshold=0.15,
        )
        print("  With threshold 0.15: %d hits" % len(hits2))
        print()


if __name__ == "__main__":
    main()
