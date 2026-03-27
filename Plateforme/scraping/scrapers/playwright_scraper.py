"""Playwright-enabled HTTP scraper fallback."""

import asyncio
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scraping.metrics import scraping_playwright_fallback_total
from scraping.scrapers.base_http_scraper import BaseHTTPScraper

logger = logging.getLogger(__name__)


class PlaywrightFallbackScraper(BaseHTTPScraper):
    """HTTP scraper with Playwright fallback for JS-heavy pages."""

    def fetch_with_fallback(self, url: str, source_name: str = "") -> tuple[str, str]:
        """Try static HTTP first, then switch to Playwright when content is weak."""
        domain = urlparse(url).netloc or "unknown"
        resolved_source = self._resolve_source_context(source_name or domain, url)
        resolved_source_name = (
            (getattr(resolved_source, "name", "") or "").strip()
            or source_name
            or domain
        )

        if bool(getattr(resolved_source, "force_playwright", False)):
            logger.info(
                "Force Playwright enabled for %s, using browser rendering",
                resolved_source_name,
            )
            scraping_playwright_fallback_total.labels(
                domain=domain,
                reason="force_playwright",
            ).inc()
            return self._playwright_fetch(url, source=resolved_source)

        char_count = 0
        status_code = None

        try:
            response = self.safe_request(
                url,
                method="GET",
                source_name=resolved_source_name,
                timeout=(3, 7),
                allow_redirects=True,
            )
            if response is None:
                logger.warning(
                    "BeautifulSoup request failed for %s - switching to Playwright",
                    url,
                )
                scraping_playwright_fallback_total.labels(
                    domain=domain,
                    reason="request_error",
                ).inc()
                return self._playwright_fetch(url, source=resolved_source)

            status_code = response.status_code
            soup = BeautifulSoup(response.text or "", "html.parser")
            char_count = len(soup.get_text(strip=True))

            if response.status_code != 200:
                logger.warning(
                    "BeautifulSoup got %s chars from %s - switching to Playwright",
                    char_count,
                    url,
                )
                scraping_playwright_fallback_total.labels(
                    domain=domain,
                    reason="status_not_200",
                ).inc()
                return self._playwright_fetch(url, source=resolved_source)

            if self.should_use_playwright(response.text):
                logger.warning(
                    "BeautifulSoup got %s chars from %s - switching to Playwright",
                    char_count,
                    url,
                )
                scraping_playwright_fallback_total.labels(
                    domain=domain,
                    reason="low_content",
                ).inc()
                return self._playwright_fetch(url, source=resolved_source)

            return response.text, "beautifulsoup"

        except requests.RequestException:
            logger.warning(
                "BeautifulSoup got %s chars from %s - switching to Playwright",
                char_count,
                url,
            )
            scraping_playwright_fallback_total.labels(
                domain=domain,
                reason="request_error",
            ).inc()
            return self._playwright_fetch(url, source=resolved_source)

    def _playwright_fetch(self, url: str, source=None) -> tuple[str, str]:
        """Render with headless Chromium and return full HTML."""

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError:
            logger.warning("Playwright package not installed while fetching %s", url)
            return "", "playwright_timeout"

        async def _run() -> tuple[str, str]:
            browser = None
            context = None
            try:
                source_context = source or getattr(self, "_current_source", None)
                if source_context is None:
                    source_context = self._resolve_source_context(
                        urlparse(url).netloc or self.name, url
                    )

                verify_ssl = bool(getattr(source_context, "verify_ssl", True))
                proxy_url = self._resolve_proxy_for_source(source_context)
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                }
                if proxy_url:
                    launch_kwargs["proxy"] = {"server": proxy_url}

                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(**launch_kwargs)
                    context = await browser.new_context(
                        ignore_https_errors=not verify_ssl,
                        user_agent=self._rotate_user_agent(),
                    )
                    page = await context.new_page()
                    await page.goto(url, timeout=15000, wait_until="networkidle")
                    await page.wait_for_load_state("domcontentloaded")
                    html = await page.content()
                    return html, "playwright"
            except PlaywrightTimeoutError:
                logger.warning("Playwright timeout while fetching %s", url)
                return "", "playwright_timeout"
            finally:
                if context is not None:
                    await context.close()
                if browser is not None:
                    await browser.close()

        try:
            return asyncio.run(_run())
        except RuntimeError:
            # Fallback for environments where an event loop is already running.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()
