import feedparser
from datetime import datetime
from scraping.scrapers.base import BaseScraper


class RSSFeedScraper:
    """
    Universal RSS/Atom feed scraper.
    Works with any website that has an RSS or Atom feed.
    """

    COMMON_FEED_PATHS = [
        "/feed",
        "/feed.xml",
        "/rss",
        "/rss.xml",
        "/atom.xml",
        "/feed/rss",
        "/blog/feed",
        "/news/feed",
        "/events/feed",
        "/index.xml",
        "/feeds/posts/default",
        "/api/feed",
    ]

    def __init__(self, base_scraper: BaseScraper):
        self.base = base_scraper

    def scrape_feed(self, feed_url, category="events"):
        """
        Scrape any RSS/Atom feed URL.
        Returns list of normalized item dicts.
        """
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            self.base._log_error("rss_scraper", str(e), feed_url)
            return []

        items = []
        feed_title = feed.feed.get("title", feed_url)

        for entry in feed.entries:
            try:
                item_dict = self._extract_entry_fields(entry, feed_url)
                item_dict["source_name"] = feed_title

                # Improvement 2: For items with short descriptions (< 200 chars),
                # try fetching the full article URL.
                if len(item_dict.get("description_en", "")) < 200:
                    full_text = self._try_fetch_full_content(item_dict["url"])
                    if full_text:
                        # Update description with full content (capped at 1000)
                        item_dict["description_en"] = full_text[:1000]

                if item_dict["title_en"] and item_dict["url"]:
                    items.append(item_dict)
            except Exception:
                continue

        return items

    def _extract_entry_fields(self, entry, feed_url):
        """
        Extract all available fields from an RSS entry
        including namespaced fields.
        """
        # Standard fields
        title = entry.get("title", "").strip()
        description = entry.get("summary", "").strip()
        url = entry.get("link", "").strip()

        # Try to get full content if available
        # (some feeds provide full_text in content tag)
        if hasattr(entry, "content") and entry.content:
            for content_item in entry.content:
                if content_item.get("type", "") in [
                    "text/html",
                    "text/plain",
                    "application/xhtml+xml",
                ]:
                    full_content = content_item.get("value", "")
                    if len(full_content) > len(description):
                        # Clean HTML tags
                        from bs4 import BeautifulSoup

                        description = BeautifulSoup(
                            full_content, "html.parser"
                        ).get_text(separator=" ", strip=True)[:1000]
                        break

        # DC namespace: dc:creator for author
        author = ""
        if hasattr(entry, "author"):
            author = entry.author
        elif hasattr(entry, "dc_creator"):
            author = entry.dc_creator

        # Media namespace: media:content for images
        image_url = ""
        if hasattr(entry, "media_content"):
            for media in entry.media_content:
                if "image" in media.get("type", ""):
                    image_url = media.get("url", "")
                    break
        elif hasattr(entry, "media_thumbnail"):
            thumbnails = entry.media_thumbnail
            if thumbnails:
                image_url = thumbnails[0].get("url", "")

        # Published date
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                from datetime import datetime

                published = datetime(*entry.published_parsed[:6])
            except Exception:
                published = None

        return {
            "title_en": title,
            "description_en": description[:1000],
            "url": url,
            "published_date": published,
            "author": author,
            "image_url": image_url,
            "source_url": feed_url,
        }

    def _try_fetch_full_content(self, item_url, max_chars=3000):
        """
        If RSS item description is too short,
        try fetching the full article page.
        Only called when description < 200 chars.
        """
        try:
            response = self.base.safe_request(item_url, timeout=15)
            if not response:
                return ""
            if response.status_code != 200:
                return ""
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            # Remove clutter
            for tag in soup(
                ["nav", "footer", "script", "style", "header", "aside"]
            ):
                tag.decompose()
            # Try to find article body
            article = (
                soup.find("article")
                or soup.find("main")
                or soup.find(class_="content")
                or soup
            )
            text = article.get_text(separator=" ", strip=True)
            return text[:max_chars]
        except Exception:
            return ""

    def detect_feed_url(self, website_url):
        """
        Auto-detect RSS/Atom feed URL from a website.
        Tries common feed URL patterns.
        Returns feed URL if found, None otherwise.
        """
        base = website_url.rstrip("/")

        for path in self.COMMON_FEED_PATHS:
            candidate = base + path
            try:
                response = self.base.safe_request(candidate, timeout=10)
                if not response:
                    continue
                if response.status_code != 200:
                    continue
                content_type = response.headers.get("Content-Type", "")
                if any(t in content_type for t in ["rss", "xml", "atom", "feed"]):
                    return candidate
                # Also try parsing as feed even without
                # correct content-type header
                parsed = feedparser.parse(response.text)
                if parsed.entries:
                    return candidate
            except Exception:
                continue

        return None
