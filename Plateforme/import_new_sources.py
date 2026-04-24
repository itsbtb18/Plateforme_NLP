import json
import os
import django
from pathlib import Path
from urllib.parse import urlparse

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from scraping.models import ScrapingSource

MD_FILE = "/app/website_to_add_to_scraping.md"
JSON_FILE = "scraping/fixtures/arabic_nlp_sources.json"

def get_name_from_url(url):
    domain = urlparse(url).netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.capitalize()

def parse_md():
    new_sources = []
    current_category = None
    
    with open(MD_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    in_added_section = False
    for line in lines:
        line = line.strip()
        if "## added websites and apis for scraper sync:" in line:
            in_added_section = True
            continue
            
        if not in_added_section:
            continue
            
        if line.startswith("### "):
            # e.g. "### events websites (arab countries and arabic nlp):"
            cat_str = line[4:].split(' ')[0].lower()
            # Map category strings if needed
            if cat_str == "apis":
                # The user added API links under 'apis', we can assign them to 'tools' or 'corpus' based on the name, 
                # or just use a generic 'tools' category
                current_category = "tools"
            elif cat_str in ["events", "news", "opportunities", "corpus", "courses", "tools"]:
                current_category = cat_str
            else:
                current_category = "events"
            continue
            
        if line.startswith("http://") or line.startswith("https://"):
            if current_category:
                url = line
                name = get_name_from_url(url)
                
                # Special naming for known ones
                if "sigarab.org" in url:
                    name = "SIGARAB " + url.split("/")[-1]
                elif "huggingface.co/api" in url:
                    name = "HuggingFace API"
                elif "api.github.com" in url:
                    name = "GitHub API"
                elif "kaggle.com" in url:
                    name = "Kaggle"
                
                new_sources.append({
                    "name": name.strip('/ ').replace('.com', '').replace('.org', '').title(),
                    "url": url,
                    "category": current_category,
                    "is_active": True,
                    "priority": 2,
                    "search_queries": [],
                    "description": f"Source added from user research for {current_category}.",
                    "language_focus": "arabic",
                    "trust_score": 0.85
                })
                
    return new_sources

def main():
    new_sources = parse_md()
    print(f"Found {len(new_sources)} new sources in the Markdown file.")
    
    # 1. Update the JSON file
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        fixture_data = json.load(f)
        
    existing_urls = {s.get("url", "").strip().lower() for s in fixture_data.get("sources", [])}
    
    added_to_json = 0
    for s in new_sources:
        if s["url"].strip().lower() not in existing_urls:
            fixture_data["sources"].append(s)
            added_to_json += 1
            
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(fixture_data, f, indent=2, ensure_ascii=False)
        
    print(f"Added {added_to_json} new sources to the JSON fixture.")
    
    # 2. Update the Database
    added_to_db = 0
    for s in new_sources:
        existing = ScrapingSource.objects.filter(url=s["url"]).first()
        if not existing:
            ScrapingSource.objects.create(
                url=s["url"],
                name=s["name"],
                category=s["category"],
                base_url=s["url"],
                is_active=True,
                description=s["description"],
                use_llm_extraction=True,
            )
            added_to_db += 1
            
    print(f"Added {added_to_db} new sources to the PostgreSQL Database.")
    print("Total sources in DB now:", ScrapingSource.objects.count())

if __name__ == '__main__':
    main()
