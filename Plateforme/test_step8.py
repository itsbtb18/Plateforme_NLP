import os
import django
import traceback
import datetime

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
    s = TestScraper()
    # Test is_event_date_valid
    print(f'Past date valid: {s.is_event_date_valid(datetime.datetime(2024, 1, 1))}')
    print(f'Future date valid: {s.is_event_date_valid(datetime.datetime(2027, 1, 1))}')
    print(f'None date valid: {s.is_event_date_valid(None)}')
    # Test validate_required_fields
    valid, missing = s.validate_required_fields({'title_en': 'Test', 'description_en': 'x' * 30}, 'courses')
    print(f'Courses validation: valid={valid} missing={missing}')
    # Test validate_and_prepare
    ok, item, reason = s.validate_and_prepare({'title_en': 'Test NLP Conference 2026', 'description_en': 'x' * 30, 'start_date': '2026-09-15'}, 'events')
    print(f'validate_and_prepare: ok={ok} reason={reason}')
except Exception:
    traceback.print_exc()
    exit(1)
