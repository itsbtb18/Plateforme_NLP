"""
NLP News scraper — sources: arXiv API (cs.CL category) and
Semantic Scholar API.

Scraped papers are stored as ``QA.Post`` instances (the platform's
existing "News" model) with ``approval_status='pending'``.

Phase 3 additions:
  - PDF download & text extraction (via ``scraping.pdf_utils``)
  - LLM-powered academic paper enrichment (summaries, keywords,
    domain classification, Arabic summary) via ``scraping.llm_validation``
"""

import logging
import re
import time
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
                        abstract=summary,
                        authors=authors_str,
                        source_url=paper_url,
                        pdf_url=pdf_url,
                        published=published,
                        categories=", ".join(categories),
                    )
                except Exception as exc:
                    logger.debug("arXiv entry parse error: %s", exc)

        except ET.ParseError as exc:
            self.errors.append(f"arXiv XML parse error: {exc}")

    # ── Semantic Scholar API ─────────────────────────────────────────
    S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
    S2_FIELDS = "title,abstract,year,url,authors,publicationDate"
    # Single broader query — avoids burning through S2's strict rate limits
    S2_QUERIES = [
        {"query": "Arabic natural language processing NLP", "year": "2024-2026", "limit": 20},
    ]

    def _scrape_semantic_scholar(self):
        """Search Semantic Scholar for recent Arabic NLP papers with rate-limit handling."""
        seen_ids: set[str] = set()

        for query_params in self.S2_QUERIES:
            params = {"fields": self.S2_FIELDS, **query_params}
            data = self._s2_request(params)
            if data is None:
                # S2 unavailable — not a hard failure, arXiv covers papers
                break

            papers = data.get("data", [])
            for paper in papers:
                paper_id = paper.get("paperId", "")
                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

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
                    abstract=abstract,
                    authors=authors_str,
                    source_url=paper_url,
                    published=pub_date,
                    year=str(year) if year else "",
                )

            # Respect rate limits — pause between queries
            time.sleep(3.5)

    def _s2_request(self, params: dict, max_retries: int = 5) -> dict | None:
        """Make a Semantic Scholar API request with 429 retry + backoff."""
        import requests as _requests

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(
                    self.S2_API, params=params, timeout=30,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 429:
                    # Use Retry-After header if provided, otherwise exponential backoff
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait = int(retry_after) + 2  # small buffer
                    else:
                        wait = min(30 * (2 ** (attempt - 1)), 180)  # 30, 60, 120, 180, 180
                    logger.warning(
                        "Semantic Scholar 429 — retrying in %ds (attempt %d/%d)",
                        wait, attempt, max_retries,
                    )
                    time.sleep(wait)
                    continue
                if resp.status_code == 504:
                    # Gateway timeout — brief retry
                    logger.warning("Semantic Scholar 504 — retrying (attempt %d/%d)", attempt, max_retries)
                    time.sleep(10 * attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except _requests.ConnectionError:
                logger.warning("Semantic Scholar connection error — retrying (attempt %d/%d)", attempt, max_retries)
                time.sleep(10 * attempt)
                continue
            except _requests.RequestException as exc:
                self.errors.append(f"Semantic Scholar request failed: {exc}")
                logger.error("Semantic Scholar request failed: %s", exc)
                return None

        logger.warning("Semantic Scholar API exhausted %d retries — skipping", max_retries)
        return None

    # ── Create Post ──────────────────────────────────────────────────
    def _create_news_post(
        self,
        *,
        title,
        abstract="",
        authors="",
        source_url="",
        pdf_url="",
        published="",
        year="",
        categories="",
    ):
        """Create a ``QA.Post`` (News) item with LLM-enriched content."""
        from QA.models import Post

        if not title:
            return

        # Duplicate check (by title similarity or URL)
        if Post.objects.filter(title_en__iexact=title).exists():
            self.items_skipped += 1
            return

        # ── PDF extraction ───────────────────────────────────────
        pdf_text = None
        if pdf_url:
            try:
                from scraping.pdf_utils import download_and_extract

                pdf_text = download_and_extract(pdf_url, session=self.session)
                if pdf_text:
                    logger.info(
                        "Extracted %d chars from PDF: %s",
                        len(pdf_text), title[:60],
                    )
            except Exception as exc:
                logger.debug("PDF extraction failed for %s: %s", title[:60], exc)

        # ── LLM enrichment ───────────────────────────────────────
        enrichment = None
        try:
            from scraping.llm_validation import (
                enrich_paper,
                build_enriched_content,
                build_enriched_content_ar,
            )

            enrichment = enrich_paper(
                title, abstract, authors=authors, pdf_text=pdf_text,
            )
            if enrichment:
                logger.info(
                    "Paper enriched — domain=%s, relevance=%.2f: %s",
                    enrichment.get("research_domain", "?"),
                    enrichment.get("arabic_nlp_relevance", 0),
                    title[:60],
                )

            content_en = build_enriched_content(
                authors=authors,
                abstract=abstract,
                source_url=source_url,
                pdf_url=pdf_url,
                published=published,
                year=year,
                categories=categories,
                enrichment=enrichment,
            )
            content_ar = build_enriched_content_ar(enrichment, fallback=abstract)

        except Exception as exc:
            logger.warning("LLM enrichment failed, using plain content: %s", exc)
            # Fallback — build plain content without enrichment
            content_en = (
                f"**Authors:** {authors}\n\n"
                f"**Abstract:** {abstract}\n\n"
                f"[Read the full paper]({source_url})"
                f"{f' | [PDF]({pdf_url})' if pdf_url else ''}"
            )
            content_ar = abstract

        # ── Title handling ───────────────────────────────────────
        title_ar = title
        if enrichment and enrichment.get("summary_ar"):
            # Use the first line of the Arabic summary as a subtitle hint,
            # but keep the original English title for title_ar since the
            # LLM returns a summary, not a translated title.
            pass

        # ── Slug generation ──────────────────────────────────────
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
                title_ar=title_ar,
                content=content_en,
                content_en=content_en,
                content_ar=content_ar,
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
                    "enriched": enrichment is not None,
                    "pdf_extracted": pdf_text is not None,
                }
            )
        except Exception as exc:
            self.errors.append(
                f"Failed to create news '{self.truncate(title, 60)}': {exc}"
            )
            logger.error("Failed to create Post %s: %s", title[:60], exc)
