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
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from django.utils.text import slugify
from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import attach_file_to_model
from scraping.field_mapping import calculate_completeness_score

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

    # Tier 1 — Algerian research institutions / ministries
    DGRSDT_BASE = "https://www.dgrsdt.dz"
    DGRSDT_PATHS = ["/actualites", "/news", "/publications"]

    MESRS_BASE = "https://www.mesrs.dz"
    MESRS_PATHS = ["/actualites", "/news", "/publications"]

    CERIST_BASE = "https://www.cerist.dz"
    CERIST_PATHS = ["/publications", "/actualites", "/news", "/recherche"]

    ALGERIAN_UNIVERSITY_RESEARCH_URLS = [
        "https://www.univ-alger.dz/recherche",
        "https://www.esi.dz/recherche",
        "https://www.usthb.dz/recherche",
        "https://www.umc.edu.dz/recherche",
    ]
    UNIVERSITY_EXTRA_PATHS = ["/publications", "/news", "/recherche"]

    NEWS_KEYWORD_HINTS = (
        "news",
        "actualite",
        "actualites",
        "publication",
        "publications",
        "recherche",
    )

    def run(self) -> dict:
        logger.info(
            "scraper_run_config",
            extra={
                "category": self.category,
                "source_name": self.name,
                "media_download_enabled": self._is_download_enabled(),
            },
        )
        return super().run()

    def scrape(self):
        try:
            from scraping.intelligence import generate_queries

            dynamic_queries = generate_queries("news")
            dynamic_terms = [
                q.get("query", "") for q in dynamic_queries if q.get("query")
            ][:5]
            if not dynamic_terms:
                dynamic_terms = ["Arabic natural language processing"]
        except Exception:
            dynamic_terms = ["Arabic natural language processing"]

        self._search_terms = dynamic_terms

        self._scrape_tier_1_algerian_research_news()
        self._scrape_tier_4_global_research_papers()

    # ── Tiered orchestration ────────────────────────────────────────
    def _scrape_tier_1_algerian_research_news(self):
        """Scrape Algerian institutional research news first (policy Tier 1)."""
        self._scrape_site_research_news(
            base_url=self.DGRSDT_BASE,
            source_name="DGRSDT",
            listing_paths=self.DGRSDT_PATHS,
            max_articles=18,
        )
        self._scrape_site_research_news(
            base_url=self.MESRS_BASE,
            source_name="MESRS",
            listing_paths=self.MESRS_PATHS,
            max_articles=18,
        )
        self._scrape_site_research_news(
            base_url=self.CERIST_BASE,
            source_name="CERIST",
            listing_paths=self.CERIST_PATHS,
            max_articles=18,
        )

        for research_url in self.ALGERIAN_UNIVERSITY_RESEARCH_URLS:
            parsed = urlparse(research_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            source_name = parsed.netloc
            root_path = parsed.path or ""

            listing_paths = [root_path] if root_path else []
            listing_paths.extend(self.UNIVERSITY_EXTRA_PATHS)
            listing_paths = [p for p in dict.fromkeys(listing_paths) if p]

            self._scrape_site_research_news(
                base_url=base_url,
                source_name=source_name,
                listing_paths=listing_paths,
                max_articles=15,
            )

    def _scrape_tier_4_global_research_papers(self):
        """Global coverage fallback (kept after Algerian-first sources)."""
        self._scrape_arxiv()
        self._scrape_semantic_scholar()

    # ── Tier 1 helpers ──────────────────────────────────────────────
    def _scrape_site_research_news(
        self,
        *,
        base_url: str,
        source_name: str,
        listing_paths: list[str],
        max_articles: int = 15,
    ):
        """RSS-first scraping with HTML listing fallback for institutional sites."""
        seen_article_urls: set[str] = set()

        # 1) RSS detection first (required policy)
        try:
            rss = self.get_rss_scraper()
            for feed_url in rss.auto_discover_feeds(base_url):
                for item in rss.parse_feed_items(feed_url, max_items=50):
                    article_url = (item.get("url") or "").strip()
                    if not article_url:
                        continue
                    normalized_url = article_url.rstrip("/")
                    if normalized_url in seen_article_urls:
                        continue
                    seen_article_urls.add(normalized_url)

                    published = ""
                    published_dt = item.get("published_date")
                    if published_dt:
                        try:
                            published = published_dt.isoformat()
                        except Exception:
                            published = str(published_dt)

                    self._create_news_post(
                        title=item.get("title", ""),
                        abstract=item.get("description", ""),
                        source_url=article_url,
                        source_name=source_name,
                        published=published,
                        thumbnail_url=item.get("image_url", ""),
                        news_category="research_news",
                    )
        except Exception as exc:
            logger.debug("RSS scraping failed for %s: %s", source_name, exc)

        # 2) HTML fallback (listing pages)
        article_candidates: list[str] = []
        for path in listing_paths:
            listing_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            resp = self.safe_request(listing_url, timeout=10, source_name=source_name)
            if resp is None:
                continue
            candidates = self._extract_candidate_article_links(
                html=resp.text,
                page_url=listing_url,
            )
            for candidate in candidates:
                key = candidate.rstrip("/")
                if key in seen_article_urls:
                    continue
                seen_article_urls.add(key)
                article_candidates.append(candidate)

        for article_url in article_candidates[:max_articles]:
            self._scrape_single_research_article(
                article_url=article_url,
                source_name=source_name,
            )

    def _extract_candidate_article_links(
        self, *, html: str, page_url: str
    ) -> list[str]:
        """Extract likely article links from a listing page."""
        soup = BeautifulSoup(html or "", "html.parser")
        parsed_page = urlparse(page_url)
        page_domain = parsed_page.netloc.lower()
        candidates: list[str] = []
        seen: set[str] = set()

        for a_tag in soup.select("a[href]"):
            href = (a_tag.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            url = urljoin(page_url, href)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc.lower() != page_domain:
                continue

            path = (parsed.path or "").lower()
            if not path or path in {"/", parsed_page.path.lower()}:
                continue
            if any(
                path.endswith(ext) for ext in (".pdf", ".jpg", ".jpeg", ".png", ".zip")
            ):
                continue
            if not any(hint in path for hint in self.NEWS_KEYWORD_HINTS):
                continue

            key = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}".rstrip(
                "/"
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(url)

        return candidates

    def _scrape_single_research_article(self, *, article_url: str, source_name: str):
        """Fetch and parse a single institutional news article page."""
        resp = self.safe_request(article_url, timeout=10, source_name=source_name)
        if resp is None:
            return

        soup = BeautifulSoup(resp.text or "", "html.parser")

        title = self._extract_article_title(soup)
        if not title:
            return

        abstract = self._extract_article_text(soup)
        if len(abstract) < 120:
            return

        published = self._extract_article_date(soup)
        thumbnail_url = self._extract_article_image(soup, article_url)

        self._create_news_post(
            title=title,
            abstract=abstract,
            source_url=article_url,
            source_name=source_name,
            published=published,
            thumbnail_url=thumbnail_url,
            news_category="research_news",
        )

    @staticmethod
    def _extract_article_title(soup: BeautifulSoup) -> str:
        for selector in [
            "meta[property='og:title']",
            "h1",
            "h2",
            "title",
        ]:
            el = soup.select_one(selector)
            if not el:
                continue
            if el.name == "meta":
                text = (el.get("content") or "").strip()
            else:
                text = el.get_text(" ", strip=True)
            if text:
                return re.sub(r"\s+", " ", text)
        return ""

    @staticmethod
    def _extract_article_text(soup: BeautifulSoup) -> str:
        # Remove noisy layout fragments first.
        for bad in soup(
            ["script", "style", "noscript", "nav", "footer", "header", "aside"]
        ):
            bad.decompose()

        main_container = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                class_=re.compile(r"content|post|article|news|actualite", re.I)
            )
            or soup
        )
        text = main_container.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text[:3500]

    @staticmethod
    def _extract_article_date(soup: BeautifulSoup) -> str:
        date_selectors = [
            "meta[property='article:published_time']",
            "meta[name='pubdate']",
            "meta[name='date']",
            "time[datetime]",
        ]
        for selector in date_selectors:
            el = soup.select_one(selector)
            if not el:
                continue
            if el.name == "time":
                value = (el.get("datetime") or "").strip()
            else:
                value = (el.get("content") or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _extract_article_image(soup: BeautifulSoup, article_url: str) -> str:
        og_image = soup.select_one("meta[property='og:image']")
        if og_image:
            content = (og_image.get("content") or "").strip()
            if content:
                return urljoin(article_url, content)

        first_img = soup.select_one("article img, main img, img")
        if first_img:
            src = (first_img.get("src") or "").strip()
            if src:
                return urljoin(article_url, src)

        return ""

    # ── arXiv API ────────────────────────────────────────────────────
    def _scrape_arxiv(self):
        """Query the arXiv API for recent cs.CL (Computation & Language) papers."""
        url = "http://export.arxiv.org/api/query"

        # Build search query from dynamic terms
        if self._search_terms:
            abs_terms = " OR ".join(
                f"abs:{term.replace(' ', '+')}" for term in self._search_terms
            )
            search_query = f"cat:cs.CL AND ({abs_terms})"
        else:
            search_query = "cat:cs.CL AND (abs:arabic OR abs:NLP OR abs:language+model)"

        params = {
            "search_query": search_query,
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
                        source_name="arXiv",
                        pdf_url=pdf_url,
                        published=published,
                        categories=", ".join(categories),
                        news_category="paper",
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
        {
            "query": "Arabic natural language processing NLP",
            "year": "2024-2026",
            "limit": 20,
        },
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
                    source_name="Semantic Scholar",
                    published=pub_date,
                    year=str(year) if year else "",
                    news_category="paper",
                )

            # Respect rate limits — pause between queries
            time.sleep(3.5)

    def _s2_request(self, params: dict, max_retries: int = 5) -> dict | None:
        """Make a Semantic Scholar API request with 429 retry + backoff."""
        import requests as _requests

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(
                    self.S2_API,
                    params=params,
                    timeout=30,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 429:
                    # Use Retry-After header if provided, otherwise exponential backoff
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait = int(retry_after) + 2  # small buffer
                    else:
                        wait = min(
                            30 * (2 ** (attempt - 1)), 180
                        )  # 30, 60, 120, 180, 180
                    logger.warning(
                        "Semantic Scholar 429 — retrying in %ds (attempt %d/%d)",
                        wait,
                        attempt,
                        max_retries,
                    )
                    time.sleep(wait)
                    continue
                if resp.status_code == 504:
                    # Gateway timeout — brief retry
                    logger.warning(
                        "Semantic Scholar 504 — retrying (attempt %d/%d)",
                        attempt,
                        max_retries,
                    )
                    time.sleep(10 * attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except _requests.ConnectionError:
                logger.warning(
                    "Semantic Scholar connection error — retrying (attempt %d/%d)",
                    attempt,
                    max_retries,
                )
                time.sleep(10 * attempt)
                continue
            except _requests.RequestException as exc:
                self.errors.append(f"Semantic Scholar request failed: {exc}")
                logger.error("Semantic Scholar request failed: %s", exc)
                return None

        logger.warning(
            "Semantic Scholar API exhausted %d retries — skipping", max_retries
        )
        return None

    # ── Create Post ──────────────────────────────────────────────────
    def _create_news_post(
        self,
        *,
        title,
        abstract="",
        authors="",
        source_url="",
        source_name="",
        pdf_url="",
        published="",
        year="",
        categories="",
        thumbnail_url="",
        news_category="paper",
    ):
        """Create a ``QA.Post`` (News) item with LLM-enriched content."""
        from QA.models import Post

        if not title:
            return

        title_en = title

        arxiv_id = ""
        if source_url:
            arxiv_match = re.search(
                r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", source_url, re.I
            )
            if arxiv_match:
                arxiv_id = arxiv_match.group(1).replace(".pdf", "")
        doi = ""
        doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", abstract or "", re.I)
        if doi_match:
            doi = doi_match.group(0)

        media_seed = {
            "title_en": title_en,
            "source_url": source_url,
            "thumbnail_url": thumbnail_url,
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id,
        }
        media_seed = self._download_media(media_seed, "news")

        is_duplicate, _ = self._check_duplicate_policy(
            "news",
            {
                "title_en": title_en,
                "arxiv_id": arxiv_id,
                "doi": doi,
                "source_url": source_url,
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return

        # ── PDF extraction ───────────────────────────────────────
        pdf_text = None
        if pdf_url:
            try:
                from scraping.pdf_utils import download_and_extract

                result = download_and_extract(pdf_url, session=self.session)
                if result is not None and (
                    isinstance(result, dict) or hasattr(result, "get")
                ):
                    if result.get("error"):
                        self._log_error(
                            "pdf_parse_failed", result.get("error"), source=pdf_url
                        )
                    pdf_text = result.get("full_text", "")
                else:
                    # backward compat: result is plain string
                    pdf_text = result or ""

                if pdf_text:
                    logger.info(
                        "pdf_extracted",
                        extra={
                            "category": self.category,
                            "source_name": source_name,
                            "item_title": title[:120],
                            "chars_extracted": len(pdf_text),
                        },
                    )
            except Exception as exc:
                logger.debug("PDF extraction failed for %s: %s", title[:60], exc)

        # ── LLM enrichment ───────────────────────────────────────
        enrichment = None
        relevance_score = None
        try:
            from scraping.llm_validation import (
                enrich_paper,
                build_enriched_content,
                build_enriched_content_ar,
            )

            enrichment = enrich_paper(
                title,
                abstract,
                authors=authors,
                pdf_text=pdf_text,
            )
            if enrichment:
                logger.info(
                    "paper_enriched",
                    extra={
                        "category": self.category,
                        "source_name": source_name,
                        "item_title": title[:120],
                        "research_domain": enrichment.get("research_domain", "?"),
                        "relevance": enrichment.get("arabic_nlp_relevance", 0),
                    },
                )
                relevance_score = enrichment.get("arabic_nlp_relevance")

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

        keywords = [k.strip() for k in str(categories or "").split(",") if k.strip()]
        authors_list = [a.strip() for a in str(authors or "").split(",") if a.strip()]
        published_date = self.parse_date(str(published)[:10]) if published else None

        item_dict = {
            "title_en": title_en,
            "title_ar": title_ar,
            "content_en": content_en,
            "content_ar": content_ar,
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id,
            "doi": doi,
            "source_url": source_url,
            "source_name": source_name or "unknown",
            "relevance_score": relevance_score,
            "thumbnail_url": thumbnail_url,
            "published_date": published_date,
            "keywords": keywords,
            "authors": authors_list,
            "news_category": news_category or "paper",
            "image_local_path": media_seed.get("image_local_path") or "",
            "image_content_file": media_seed.get("image_content_file"),
            "pdf_local_path": media_seed.get("pdf_local_path") or "",
            "pdf_content_file": media_seed.get("pdf_content_file"),
        }

        item_dict = enrich_scraped_item(item_dict, "news")
        completeness = calculate_completeness_score(item_dict, "news")

        if completeness < 50:
            self.items_skipped += 1
            return

        item_dict["published_date"] = published_date
        item_dict["publication_date"] = published
        item_dict["date"] = published

        is_valid, item_dict, reason = self.validate_and_prepare(item_dict, "news")
        if not is_valid:
            self.items_skipped += 1
            logger.debug("Skipping news '%s' due to validation: %s", title, reason)
            return

        try:
            post = Post.objects.create(
                title=item_dict.get("title_en", "")[:300],
                title_en=item_dict.get("title_en", "")[:300],
                title_ar=item_dict.get("title_ar", "")[:300],
                content=item_dict.get("content_en", ""),
                content_en=item_dict.get("content_en", ""),
                content_ar=item_dict.get("content_ar", ""),
                arxiv_id=item_dict.get("arxiv_id", ""),
                doi=item_dict.get("doi", ""),
                source_url=item_dict.get("source_url", ""),
                source_name=item_dict.get("source_name", ""),
                relevance_score=item_dict.get("relevance_score"),
                published_date=self.parse_date(
                    str(item_dict.get("published_date", ""))[:10]
                )
                if item_dict.get("published_date")
                else None,
                authors=item_dict.get("authors") or None,
                news_category=item_dict.get("news_category") or "paper",
                slug=slug,
                approval_status="pending",
                author=self.get_system_user(),
            )

            pdf_local_path = item_dict.get("pdf_local_path") or ""
            if pdf_local_path:
                try:
                    attach_file_to_model(
                        post,
                        "file",
                        item_dict.get("pdf_content_file"),
                        pdf_local_path,
                    )
                except Exception:
                    pass

            image_local_path = item_dict.get("image_local_path") or ""
            if image_local_path:
                try:
                    attach_file_to_model(
                        post,
                        "thumbnail",
                        item_dict.get("image_content_file"),
                        image_local_path,
                    )
                except Exception:
                    try:
                        attach_file_to_model(
                            post,
                            "image",
                            item_dict.get("image_content_file"),
                            image_local_path,
                        )
                    except Exception:
                        pass

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 100),
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
