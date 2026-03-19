import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
try:
    django.setup()
except Exception:
    traceback.print_exc()
    exit(1)

from scraping.intelligence import compute_relevance_score
test_item = {
    'title_en': 'Test Arabic NLP Paper',
    'published_date': '2025-01-15',
    'source': 'arxiv',
}
try:
    score = compute_relevance_score(text=test_item['title_en'], created_date=test_item['published_date'])
    print(f'Score computed successfully: {score}')
except Exception as e:
    print(f'ERROR - date math still broken: {e}')
    traceback.print_exc()
