import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from scraping.scrapers.base import BaseScraper

class TestScraper(BaseScraper):
    def scrape(self):
        return []

scraper = TestScraper()
user = scraper.get_system_user()
print(f'System user: {user}')
print(f'User email: {getattr(user, "email", None)}')
print(f'User is None: {user is None}')
