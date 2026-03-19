import re
from bs4 import BeautifulSoup
from scraping.scrapers.base import BaseScraper


class CustomDomainScraper(BaseScraper):
    """
    Scrapes any custom domain added by admin.
    Uses LLM to extract structured data from unknown layouts.
    Falls back to RSS if available.
    """

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.category = source.category
        self.items_failed = 0

    def scrape(self):
        results = []

        # Step 1: try RSS first if enabled
        if self.source.use_rss:
            rss_scraper = self.get_rss_scraper()
            feed_url = rss_scraper.detect_feed_url(self.source.base_url)
            if feed_url:
                rss_items = rss_scraper.scrape_feed(feed_url, self.source.category)
                if rss_items:
                    results.extend(self._save_rss_items(rss_items))
                    return results

        # Step 2: HTML scraping with LLM extraction
        response = self.safe_request(self.source.base_url)
        if not response:
            return results

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove nav, footer, scripts
        for tag in soup([
            'nav', 'footer', 'script', 'style', 'header',
            'aside', 'advertisement', 'ads', 'cookie',
            'popup', 'modal', 'sidebar', 'menu',
            '[class*="nav"]', '[class*="menu"]',
            '[class*="footer"]', '[class*="header"]',
            '[class*="ad"]', '[class*="cookie"]',
            '[id*="nav"]', '[id*="menu"]',
            '[id*="footer"]', '[id*="header"]',
        ]):
            tag.decompose()

        # Try to find main content container
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find(id='content') or
            soup.find(id='main') or
            soup.find(class_='content') or
            soup.find(class_='main') or
            soup  # fallback to full page
        )

        # Extract clean text for LLM
        clean_html = str(soup)[:12000]  # noqa: F841
        page_text = main_content.get_text(separator="\n", strip=True)[:12000]

        if self.source.use_llm_extraction:
            items = self._extract_with_llm(page_text)
        else:
            items = self._extract_with_selectors(soup, self.source.scrape_config)

        for item in items:
            try:
                result = self._save_item(item)
                if result:
                    results.append(result)
                else:
                    self.items_skipped += 1
            except Exception as e:
                self.items_failed = getattr(self, "items_failed", 0) + 1
                self._log_error(
                    "custom_scraper_save", str(e), source=item.get("title", "unknown")
                )

        return results

    def _extract_with_llm(self, page_text):
        from scraping.llm_validation import GroqLLMClient

        client = GroqLLMClient()

        category_hints = {
            "events": "conferences, workshops, hackathons, events",
            "tools": "NLP tools, software, libraries, models",
            "news": "research papers, articles, news",
            "courses": "courses, tutorials, training programs",
            "institutions": "universities, labs, research centers",
        }
        hint = category_hints.get(self.source.category, "items")

        prompt = f"""
You are a data extraction specialist for an Arabic NLP
research platform.

Extract ALL {hint} found in this webpage text.
Return ONLY a valid JSON array, no other text.

Each item must have these fields:
- title (string, required, 5-300 chars)
- description (string, max 500 chars, can be empty "")
- url (string, full URL starting with http, or "")
- date (string, ISO format YYYY-MM-DD if found, or null)
- location (string, city/country if found, or "")

Important:
- Extract ALL items you find, not just the first one
- If a field is not available, use "" or null
- Do not invent information not present in the text
- Return [] if no {hint} are found

Webpage text:
{page_text}

Return ONLY the JSON array:
"""
        try:
            response_text = client._chat(prompt)
            import json

            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return []

    def _extract_with_selectors(self, soup, config):
        items = []
        title_sel = config.get("title_selector", "h2, h3")
        desc_sel = config.get("desc_selector", "p")
        link_sel = config.get("link_selector", "a")  # noqa: F841

        titles = soup.select(title_sel)
        for t in titles[:20]:
            item = {
                "title": t.get_text(strip=True),
                "description": "",
                "url": "",
                "date": None,
            }
            next_p = t.find_next(desc_sel.split(",")[0].strip())
            if next_p:
                item["description"] = next_p.get_text(strip=True)[:300]
            link = t.find("a") or t.find_next("a")
            if link and link.get("href"):
                item["url"] = link["href"]
            if item["title"]:
                items.append(item)
        return items

    def _save_rss_items(self, rss_items):
        saved = []
        for item in rss_items:
            result = self._save_item(
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "url": item.get("url", ""),
                    "date": item.get("published_date"),
                }
            )
            if result:
                saved.append(result)
        return saved

    def _save_item(self, item):
        """
        Save item to the appropriate model based on category.
        Returns item dict if created, None if skipped.
        """
        title = item.get("title", "").strip()
        if not title or len(title) < 3:
            return None

        try:
            if self.source.category == "events":
                return self._save_as_event(item)
            elif self.source.category == "news":
                return self._save_as_news(item)
            else:
                return item
        except Exception as e:
            self._log_error("custom_save", str(e), source=title)
            return None

    def _save_as_event(self, item):
        from events.models import Event

        title = item.get("title", "").strip()
        if not title:
            return None
        if Event.objects.filter(title_en__iexact=title).exists():
            return None

        event = Event.objects.create(
            title_en=title[:200],
            title_ar=title[:200],
            description_en=item.get("description", "")[:1000],
            description_ar=item.get("description", "")[:1000],
            website=item.get("url", ""),
            approval_status="pending",
            created_by=self.get_system_user(),
            source="custom_scrape",
        )
        return {"title_en": title, "id": str(event.id)}

    def _save_as_news(self, item):
        from QA.models import Post

        title = item.get("title", "").strip()
        if not title:
            return None
        if Post.objects.filter(title_en__iexact=title).exists():
            return None

        post = Post.objects.create(
            title_en=title[:200],
            title_ar=title[:200],
            content_en=item.get("description", ""),
            content_ar=item.get("description", ""),
            approval_status="pending",
            author=self.get_system_user(),
        )
        return {"title_en": title, "id": str(post.id)}
