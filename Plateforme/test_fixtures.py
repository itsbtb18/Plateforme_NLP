import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from scraping.scrapers.courses import CourseScraper, CURATED_COURSES
from scraping.scrapers.institutions import InstitutionScraper

cs = CourseScraper()
print(f"Curated courses loaded: {len(CURATED_COURSES)}")
print(f"Coursera courses loaded: {len(cs.COURSERA_COURSES)}")
print(f"YouTube playlists loaded: {len(cs.YOUTUBE_PLAYLISTS)}")

print("---")

inst = InstitutionScraper()
print(f"Algerian universities loaded: {len(inst.ALGERIAN_UNIVERSITIES)}")
print(f"African NLP labs loaded: {len(inst.AFRICAN_NLP_LABS)}")
print(f"North African institutions loaded: {len(inst.NORTH_AFRICAN_INSTITUTIONS)}")
print(f"Arabic institutions loaded: {len(inst.ARABIC_INSTITUTIONS)}")
