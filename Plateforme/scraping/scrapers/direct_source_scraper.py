import asyncio
import httpx
import logging
from bs4 import BeautifulSoup
from typing import Any
import re

logger = logging.getLogger(__name__)

class DirectSourceScraper:
    """
    FIX: Manual scraping of high-quality sources for Events and Opportunities
    to bypass Tavily non-indexing issues.
    """
    
    EVENTS_SOURCES = [
        "https://aclanthology.org/events/",
        "https://www.wikicfp.com/cfp/call?conference=nlp",
        "https://aclweb.org/aclwiki/ACL_Events",
    ]
    
    OPPORTUNITIES_SOURCES = [
        "https://euraxess.ec.europa.eu/jobs/search?keywords=NLP",
        "https://euraxess.ec.europa.eu/jobs/search?keywords=natural+language+processing",
        "https://academicpositions.eu/ad/search?keyword=NLP",
    ]

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def get_sources_for_category(self, category: str) -> list[str]:
        if category == "events":
            return self.EVENTS_SOURCES
        if category == "opportunities":
            return self.OPPORTUNITIES_SOURCES
        return []

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            resp = await client.get(url, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"DirectSourceScraper: Failed to fetch {url}: {e}")
            return ""

    async def scrape_events(self) -> list[dict]:
        """Scrappe directement les sources d'events NLP connues."""
        candidates = []
        async with httpx.AsyncClient(headers=self.headers, verify=False) as client:
            tasks = [self._fetch(client, url) for url in self.EVENTS_SOURCES]
            pages = await asyncio.gather(*tasks)
            
            for i, html in enumerate(pages):
                if not html: continue
                source_url = self.EVENTS_SOURCES[i]
                soup = BeautifulSoup(html, "html.parser")
                
                # Simple heuristic extraction based on common patterns
                if "wikicfp" in source_url:
                    rows = soup.select(".contittr tr")
                    for row in rows:
                        link = row.select_one("a[href*='/cfp/servlet/event.showcfp']")
                        if link:
                            title = link.get_text(strip=True)
                            url = "http://www.wikicfp.com" + link['href']
                            candidates.append({
                                "title": title,
                                "url": url,
                                "content": f"NLP Event from WikiCFP: {title}",
                                "score": 0.9
                            })
                elif "aclanthology" in source_url:
                    # ACL Anthology events are in <h4> or <a> inside certain divs
                    links = soup.select("a")
                    for link in links:
                        title = link.get_text(strip=True)
                        href = link.get('href', '')
                        if any(kw in title.lower() for kw in ["acl 2", "emnlp", "naacl", "coling", "eacl"]):
                            url = "https://aclanthology.org" + href if href.startswith("/") else href
                            candidates.append({
                                "title": title,
                                "url": url,
                                "content": f"Major NLP Conference: {title}",
                                "score": 0.95
                            })
                else:
                    # Generic link extraction
                    for link in soup.find_all("a", href=True):
                        href = link['href']
                        text = link.get_text(strip=True)
                        if len(text) > 8 and any(kw in text.lower() for kw in ["nlp", "conference", "workshop", "symposium", "call for papers"]):
                            candidates.append({
                                "title": text,
                                "url": href if href.startswith("http") else source_url + href,
                                "content": f"Potential NLP event: {text}",
                                "score": 0.7
                            })
                            
        return candidates[:30]

    async def scrape_opportunities(self) -> list[dict]:
        """Scrappe directement EURAXESS et autres sources."""
        candidates = []
        async with httpx.AsyncClient(headers=self.headers, verify=False) as client:
            tasks = [self._fetch(client, url) for url in self.OPPORTUNITIES_SOURCES]
            pages = await asyncio.gather(*tasks)
            
            for i, html in enumerate(pages):
                if not html: continue
                source_url = self.OPPORTUNITIES_SOURCES[i]
                soup = BeautifulSoup(html, "html.parser")
                
                if "euraxess" in source_url:
                    # EURAXESS jobs search results often have titles in <h3> or <a> with specific classes
                    links = soup.select("a")
                    for link in links:
                        title = link.get_text(strip=True)
                        href = link.get('href', '')
                        if "/jobs/" in href and len(title) > 20:
                            url = "https://euraxess.ec.europa.eu" + href if href.startswith("/") else href
                            candidates.append({
                                "title": title,
                                "url": url,
                                "content": f"Euraxess Research Job: {title}",
                                "score": 0.9
                            })
                else:
                    # Generic job links
                    for link in soup.find_all("a", href=True):
                        href = link['href']
                        text = link.get_text(strip=True)
                        if len(text) > 15 and any(kw in text.lower() for kw in ["postdoc", "phd", "researcher", "lecturer", "professor"]):
                            candidates.append({
                                "title": text,
                                "url": href if href.startswith("http") else source_url + href,
                                "content": f"Academic Position: {text}",
                                "score": 0.8
                            })
                            
        return candidates[:30]
