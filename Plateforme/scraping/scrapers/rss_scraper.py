import feedparser
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraping.scrapers.base import BaseScraper


class RSSFeedScraper:
    """
    Universal RSS/Atom feed scraper.
    Works with any website that has an RSS or Atom feed.
    """

    COMMON_FEED_PATHS = [
        "/feed",
        "/rss",
        "/atom.xml",
        "/feed.xml",
        "/rss.xml",
        "/news/feed",
        "/blog/feed",
    ]

    def __init__(self, base_scraper: BaseScraper):
        self.base = base_scraper

    def auto_discover_feeds(self, url) -> list[str]:
        """
        Discover RSS/Atom feeds for a website URL.

        Strategy:
          1) try common feed paths
          2) parse homepage <link rel="alternate" ...> tags

        Returns a unique list of discovered feed URLs.
        Never raises.
        """
        base_url = (url or "").strip().rstrip("/")
        if not base_url:
            return []

        discovered = []
        seen = set()

        def _add_feed(candidate_url: str):
            normalized = (candidate_url or "").strip()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            discovered.append(normalized)

        # 1) Probe common feed paths.
        for path in self.COMMON_FEED_PATHS:
            candidate = urljoin(base_url + "/", path.lstrip("/"))
            try:
                response = self.base.safe_request(
                    candidate,
                    timeout=10,
                    source_name="rss_auto_discovery",
                )
                if not response or response.status_code >= 400:
                    continue

                content_type = (response.headers.get("Content-Type") or "").lower()
                is_xml_like = any(
                    token in content_type
                    for token in ("rss", "atom", "xml", "application/feed")
                )
                if is_xml_like:
                    _add_feed(response.url or candidate)
                    continue

                parsed = feedparser.parse(response.text)
                if parsed.entries:
                    _add_feed(response.url or candidate)
            except Exception:
                continue

        # 2) Parse <link rel="alternate" ...> from the main page HTML.
        try:
            response = self.base.safe_request(
                base_url,
                timeout=10,
                source_name="rss_auto_discovery",
            )
            if response and response.status_code < 400:
                soup = BeautifulSoup(response.text or "", "html.parser")
                for link in soup.select("link[rel]"):
                    rel_attr = link.get("rel") or []
                    rel_values = [str(v).lower() for v in rel_attr]
                    if "alternate" not in rel_values:
                        continue

                    feed_type = (link.get("type") or "").lower().strip()
                    if feed_type not in (
                        "application/rss+xml",
                        "application/atom+xml",
                    ):
                        continue

                    href = (link.get("href") or "").strip()
                    if not href:
                        continue
                    _add_feed(urljoin(base_url + "/", href))
        except Exception:
            return discovered

        return discovered

    def parse_feed_items(self, feed_url, max_items=50) -> list[dict]:
        """
        Parse RSS/Atom feed items and normalize to a common schema.

        Output keys:
          title, description, url, published_date, author, image_url

        Returns an empty list on any failure.
        Never raises.
        """
        try:
            parsed = feedparser.parse(feed_url)
            entries = parsed.entries or []
        except Exception:
            return []

        items = []
        for entry in entries[: max(int(max_items or 50), 0)]:
            try:
                title = (entry.get("title") or "").strip()
                url = (entry.get("link") or entry.get("id") or "").strip()

                description = (entry.get("summary") or "").strip()
                if not description and entry.get("content"):
                    content_nodes = entry.get("content") or []
                    if content_nodes:
                        description = (content_nodes[0].get("value") or "").strip()
                if description:
                    description = BeautifulSoup(description, "html.parser").get_text(
                        separator=" ", strip=True
                    )

                published_date = None
                time_value = entry.get("published_parsed") or entry.get(
                    "updated_parsed"
                )
                if time_value:
                    try:
                        published_date = datetime(*time_value[:6])
                    except Exception:
                        published_date = None

                author = (entry.get("author") or "").strip() or (
                    entry.get("dc_creator") or ""
                ).strip()

                image_url = ""
                media_content = entry.get("media_content") or []
                for media in media_content:
                    media_type = (media.get("type") or "").lower()
                    media_url = (media.get("url") or "").strip()
                    if media_url and ("image" in media_type or not media_type):
                        image_url = media_url
                        break

                if not image_url:
                    media_thumbs = entry.get("media_thumbnail") or []
                    if media_thumbs:
                        image_url = (media_thumbs[0].get("url") or "").strip()

                if not image_url:
                    for link in entry.get("links") or []:
                        href = (link.get("href") or "").strip()
                        link_type = (link.get("type") or "").lower()
                        if href and "image" in link_type:
                            image_url = href
                            break

                if not title and not url:
                    continue

                items.append(
                    {
                        "title": title,
                        "description": description,
                        "url": url,
                        "published_date": published_date,
                        "author": author,
                        "image_url": image_url,
                    }
                )
            except Exception:
                continue

        return items

    def scrape_feed(self, feed_url, category="events"):
        """
        Scrape any RSS/Atom feed URL.
        Returns list of normalized item dicts.
        """
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get("title", feed_url)
        except Exception as e:
            self.base._log_error("rss_scraper", str(e), feed_url)
            return []

        parsed_items = self.parse_feed_items(feed_url)
        items = []
        for parsed_item in parsed_items:
            try:
                item_dict = {
                    "title_en": parsed_item.get("title", ""),
                    "description_en": parsed_item.get("description", "")[:1000],
                    "url": parsed_item.get("url", ""),
                    "published_date": parsed_item.get("published_date"),
                    "author": parsed_item.get("author", ""),
                    "image_url": parsed_item.get("image_url", ""),
                    "source_url": feed_url,
                }
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
            for tag in soup(["nav", "footer", "script", "style", "header", "aside"]):
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
        discovered = self.auto_discover_feeds(website_url)
        return discovered[0] if discovered else None
