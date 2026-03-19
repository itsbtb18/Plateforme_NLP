import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
try:
    django.setup()
except Exception:
    traceback.print_exc()
    exit(1)

try:
    from scraping.scrapers.base import BaseScraper
    class TestScraper(BaseScraper):
        def scrape(self): return []
    scraper = TestScraper()
    rss = scraper.get_rss_scraper()
    print(f'RSS scraper created: {rss}')
    print(f'COMMON_FEED_PATHS count: {len(rss.COMMON_FEED_PATHS)}')
except Exception:
    traceback.print_exc()
    exit(1)
