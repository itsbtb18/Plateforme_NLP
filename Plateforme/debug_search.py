import asyncio
import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from scraping.network.search_client import TavilySearchClient

async def debug_search():
    client = TavilySearchClient()
    print(f"Client enabled: {client.is_enabled}")
    if not client.is_enabled:
        print(f"Disabled reason: {client.disabled_reason}")
        return
        
    query = "15th International Conference on Natural Language Processing (NLP 2026)"
    print(f"Searching for: {query}")
    
    results = await client.search_events(query, max_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"- {r.get('url')}")

if __name__ == "__main__":
    asyncio.run(debug_search())
