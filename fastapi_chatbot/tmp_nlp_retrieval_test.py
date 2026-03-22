import asyncio

from app.db import AsyncSessionLocal
from app.services.retrieval.search import search_nlp_knowledge


async def main():
    async with AsyncSessionLocal() as db:
        for query, lang in [
            ("Explain transformer architecture in NLP", "en"),
            ("اشرح بنية Transformer في معالجة اللغة الطبيعية", "ar"),
        ]:
            results = await search_nlp_knowledge(query, db, language=lang)
            print("query", query)
            print("lang", lang, "count", len(results))
            if results:
                print("first_title", str(results[0].get("title", ""))[:80])
            print("---")


if __name__ == "__main__":
    asyncio.run(main())
