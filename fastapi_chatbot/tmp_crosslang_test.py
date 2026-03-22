import asyncio

from app.db import AsyncSessionLocal
from app.services.retrieval.search import search_legal_documents


async def main():
    async with AsyncSessionLocal() as db:
        query = "ما هي إجراءات تغيير مشرف الأطروحة إذا توفي المشرف؟"
        results = await search_legal_documents(query, db, language="ar")
        print("count", len(results))
        print("langs", [r.get("language") for r in results[:10]])
        print("titles", [str(r.get("title", ""))[:90] for r in results[:3]])


if __name__ == "__main__":
    asyncio.run(main())
