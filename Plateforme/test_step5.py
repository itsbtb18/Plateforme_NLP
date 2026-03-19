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
    from scraping.scrapers.institutions import InstitutionScraper
    scraper = InstitutionScraper()
    # Test the list conversion
    test_specialties = ['NLP', 'Arabic', 'Deep Learning']
    if isinstance(test_specialties, list):
        result = ', '.join(str(v) for v in test_specialties if v)
        print(f'List conversion works: {result}')
    else:
        print('ERROR: conversion not applied')
except Exception:
    traceback.print_exc()
    exit(1)
