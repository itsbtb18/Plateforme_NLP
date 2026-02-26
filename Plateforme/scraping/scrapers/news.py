"""
NLP News scraper — sources: arXiv API (cs.CL category) and
Semantic Scholar API.

Scraped papers are stored as ``QA.Post`` instances (the platform's
existing "News" model) with ``approval_status='pending'``.
"""

import logging
import re
import xml.etree.ElementTree as ET
from django.utils.text import slugify
from .base import BaseScraper

logger = logging.getLogger(__name__)

# arXiv Atom namespace
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class NewsScraper(BaseScraper):
    """Scrape recent NLP papers/news from arXiv and Semantic Scholar."""

    name = "NLP News & Papers"
    category = "news"

    def scrape(self):
        self._scrape_arxiv()
        self._scrape_semantic_scholar()

    # ── arXiv API ────────────────────────────────────────────────────
    def _scrape_arxiv(self):
        """Query the arXiv API for recent cs.CL (Computation & Language) papers."""
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": "cat:cs.CL AND (abs:arabic OR abs:NLP OR abs:language+model)",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": 20,
            "start": 0,
        }
        resp = self.safe_request(url, params=params)
        if resp is None:
            return

        try:
            root = ET.fromstring(resp.content)
            entries = root.findall("atom:entry", ARXIV_NS)

            for entry in entries:
                try:
                    title = (entry.findtext("atom:title", "", ARXIV_NS) or "").strip()
                    title = re.sub(r"\s+", " ", title)

                    summary = (
                        entry.findtext("atom:summary", "", ARXIV_NS) or ""
                    ).strip()
                    summary = re.sub(r"\s+", " ", summary)

                    published = entry.findtext("atom:published", "", ARXIV_NS)

                    # Collect author names
                    authors_el = entry.findall("atom:author", ARXIV_NS)
                    authors = [
                        a.findtext("atom:name", "", ARXIV_NS) for a in authors_el
                    ]
                    authors_str = ", ".join(authors[:5])
                    if len(authors) > 5:
                        authors_str += f" (+{len(authors) - 5} more)"

                    # Links
                    paper_url = ""
                    pdf_url = ""
                    for link in entry.findall("atom:link", ARXIV_NS):
                        rel = link.get("rel", "")
                        href = link.get("href", "")
                        link_type = link.get("type", "")
                        if rel == "alternate":
                            paper_url = href
                        elif link_type == "application/pdf":
                            pdf_url = href

                    # Categories
                    categories = [
                        c.get("term", "")
                        for c in entry.findall("atom:category", ARXIV_NS)
                    ]

                    self._create_news_post(
                        title=title,
                        content=(
                            f"**Authors:** {authors_str}\n\n"
                            f"**Abstract:** {summary}\n\n"
                            f"**Categories:** {', '.join(categories)}\n\n"
                            f"[Read the full paper]({paper_url})"
                            f"{f' | [PDF]({pdf_url})' if pdf_url else ''}"
                        ),
                        source_url=paper_url,
                        published=published,
                    )
                except Exception as exc:
                    logger.debug("arXiv entry parse error: %s", exc)

        except ET.ParseError as exc:
            self.errors.append(f"arXiv XML parse error: {exc}")

    # ── Semantic Scholar API ─────────────────────────────────────────
    def _scrape_semantic_scholar(self):
        """Search Semantic Scholar for recent Arabic NLP papers."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": "Arabic natural language processing",
            "limit": 15,
            "fields": "title,abstract,year,url,authors,publicationDate",
            "year": "2024-2025",
        }
        resp = self.safe_request(url, params=params)
        if resp is None:
            return

        try:
            data = resp.json()
            papers = data.get("data", [])

            for paper in papers:
                title = paper.get("title", "")
                abstract = paper.get("abstract", "") or ""
                paper_url = paper.get("url", "")
                pub_date = paper.get("publicationDate", "")
                year = paper.get("year", "")

                authors_list = paper.get("authors", [])
                authors_str = ", ".join(a.get("name", "") for a in authors_list[:5])
                if len(authors_list) > 5:
                    authors_str += f" (+{len(authors_list) - 5} more)"

                self._create_news_post(
                    title=title,
                    content=(
                        f"**Authors:** {authors_str}\n\n"
                        f"**Year:** {year}\n\n"
                        f"**Abstract:** {abstract}\n\n"
                        f"[View on Semantic Scholar]({paper_url})"
                    ),
                    source_url=paper_url,
                    published=pub_date,
                )
        except Exception as exc:
            self.errors.append(f"Semantic Scholar error: {exc}")
            logger.error("Semantic Scholar API error: %s", exc)

    # ── Create Post ──────────────────────────────────────────────────
    def _create_news_post(self, *, title, content, source_url="", published=""):
        """Create a ``QA.Post`` (News) item with pending approval."""
        from QA.models import Post

        if not title:
            return

        # Duplicate check (by title similarity or URL)
        if Post.objects.filter(title_en__iexact=title).exists():
            self.items_skipped += 1
            return
        slug = slugify(title[:190])
        if not slug:
            slug = slugify(title[:190].encode("ascii", "ignore").decode())
        if not slug:
            import uuid as _uuid

            slug = str(_uuid.uuid4())[:8]

        # Ensure slug uniqueness
        base_slug = slug
        counter = 1
        while Post.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            Post.objects.create(
                title=title,
                title_en=title,
                title_ar=title,
                content=content,
                content_en=content,
                content_ar=content,
                slug=slug,
                author=self.get_system_user(),
                approval_status="pending",
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(title, 100),
                    "url": source_url,
                    "published": str(published)[:10] if published else "",
                }
            )
        except Exception as exc:
            self.errors.append(
                f"Failed to create news '{self.truncate(title, 60)}': {exc}"
            )
            logger.error("Failed to create Post %s: %s", title[:60], exc)
