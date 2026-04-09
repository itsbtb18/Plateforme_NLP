import asyncio
from collections import Counter

from app.db import AsyncSessionLocal
from app.services.retrieval.search import search_nlp_knowledge


async def main() -> None:
    query = "bert gpt arabic nlp differences"
    async with AsyncSessionLocal() as db:
        docs = await search_nlp_knowledge(query, db, top_k=12, language="ar")

    by_file = Counter((d.get("source_file") or "unknown") for d in docs)
    print("PROBE_OK")
    print("retrieved_docs=", len(docs))
    print("distinct_source_files=", len(by_file))
    for name, count in by_file.most_common(12):
        print(f"- {name}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
