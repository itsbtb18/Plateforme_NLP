import json
import ast

def extract_list(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    import re
    match = re.search(f"{var_name}\s*=\s*(\[.*?\])\n\s*(?:[A-Za-z0-9_]+\s*=|def |#)", text, re.DOTALL)
    if not match:
        match = re.search(f"{var_name}\s*=\s*(\[.*?\])\s*$", text, re.DOTALL)
    if not match:
        return []
    try:
        return ast.literal_eval(match.group(1))
    except:
        return []

def extract_str(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    import re
    match = re.search(f'{var_name}\s*=\s*[\'"]([^\'"]+)[\'"]', text)
    if match:
        return match.group(1)
    return ""

def extract_dict(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    import re
    match = re.search(f"{var_name}\s*=\s*(\{{.*?\}})\n\s*(?:class|def)", text, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group(1))
        except:
            pass
    return {}

sources = []
def add_source(section, name, url, stype, tier=1, notes='', country='global'):
    sources.append({
        'section': section,
        'name': name,
        'url': url,
        'scraper_type': stype,
        'is_active': True,
        'is_default': True,
        'tier': tier,
        'country': country,
        'schedule_cron': '0 6 * * *',
        'selector_title': '',
        'selector_body': '',
        'selector_date': '',
        'selector_author': '',
        'notes': notes
    })


# 1. seed_scraping_sources.py
seed_dict = extract_dict('scraping/management/commands/seed_scraping_sources.py', 'DEFAULT_SOURCES')
for section, items in seed_dict.items():
    for name, url, stype in items:
        add_source(section, name, url, stype, tier=1, notes="Imported from seed")


# 2. news.py
n_dgrsdt = extract_str('scraping/scrapers/news.py', 'DGRSDT_BASE')
if n_dgrsdt: add_source('news', 'DGRSDT', n_dgrsdt, 'web', 1, 'Algerian Research', 'DZ')

n_mesrs = extract_str('scraping/scrapers/news.py', 'MESRS_BASE')
if n_mesrs: add_source('news', 'MESRS', n_mesrs, 'web', 1, 'Algerian Research', 'DZ')

n_cerist = extract_str('scraping/scrapers/news.py', 'CERIST_BASE')
if n_cerist: add_source('news', 'CERIST', n_cerist, 'web', 1, 'Algerian Research', 'DZ')

n_univ = extract_list('scraping/scrapers/news.py', 'ALGERIAN_UNIVERSITY_RESEARCH_URLS')
for u in n_univ:
    name = u.replace('https://www.','').split('.')[0].upper()
    add_source('news', f'{name} Research', u, 'web', 1, 'Algerian University', 'DZ')


# 3. courses.py
for t1 in extract_list('scraping/scrapers/courses.py', 'TIER_1_RSS_SOURCES'):
    add_source('courses', t1['source_name'], t1['base_url'], 'rss', 1, 'University', t1['country_code'])
for t2 in extract_list('scraping/scrapers/courses.py', 'TIER_2_RSS_SOURCES'):
    add_source('courses', t2['source_name'], t2['base_url'], 'rss', 2, 'Online platform', t2['country_code'])
for t3 in extract_list('scraping/scrapers/courses.py', 'TIER_3_RSS_SOURCES'):
    add_source('courses', t3['source_name'], t3['base_url'], 'rss', 3, 'Global', t3['country_code'])

c_cerist = extract_str('scraping/scrapers/courses.py', 'CERIST_FORMATION_URL')
if c_cerist: add_source('courses', 'CERIST Formation', c_cerist, 'web', 1, 'Algerian', 'DZ')

c_fun = extract_str('scraping/scrapers/courses.py', 'FUN_MOOC_API')
if c_fun: add_source('courses', 'FUN MOOC API', c_fun, 'api', 2, 'MOOC')

c_mit = extract_str('scraping/scrapers/courses.py', 'MIT_API_BASE')
if c_mit: add_source('courses', 'MIT Direct API', c_mit, 'api', 3, 'MIT')

# 4. institutions.py
for ilab in extract_list('scraping/scrapers/institutions.py', 'TOP_GLOBAL_LABS'):
    add_source('institutions', ilab['name'], ilab['website'], 'web', 4, 'Top NLP lab', ilab['country_code'])

for r1 in extract_list('scraping/scrapers/institutions.py', 'TIER_1_RSS_SOURCES'):
    add_source('institutions', r1['source_name'], r1['base_url'], 'rss', 1, 'RSS Source', r1['country_code'])
for r2 in extract_list('scraping/scrapers/institutions.py', 'TIER_2_RSS_SOURCES'):
    add_source('institutions', r2['source_name'], r2['base_url'], 'rss', 2, 'RSS Source', r2['country_code'])
for r3 in extract_list('scraping/scrapers/institutions.py', 'TIER_3_RSS_SOURCES'):
    add_source('institutions', r3['source_name'], r3['base_url'], 'rss', 3, 'RSS Source', r3['country_code'])
for r4 in extract_list('scraping/scrapers/institutions.py', 'TIER_4_RSS_SOURCES'):
    add_source('institutions', r4['source_name'], r4['base_url'], 'rss', 4, 'RSS Source', r4['country_code'])

# 5. tools.py
for rt1 in extract_list('scraping/scrapers/tools.py', 'TIER_1_RSS_SOURCES'):
    if isinstance(rt1, list) or isinstance(rt1, tuple): add_source('tools', rt1[1], rt1[0], 'rss', 1)
for rt2 in extract_list('scraping/scrapers/tools.py', 'TIER_2_RSS_SOURCES'):
    if isinstance(rt2, list) or isinstance(rt2, tuple): add_source('tools', rt2[1], rt2[0], 'rss', 2)
for rt3 in extract_list('scraping/scrapers/tools.py', 'TIER_3_RSS_SOURCES'):
    if isinstance(rt3, list) or isinstance(rt3, tuple): add_source('tools', rt3[1], rt3[0], 'rss', 3)


import os
os.makedirs('scraping/fixtures', exist_ok=True)
with open('scraping/fixtures/default_sources.json', 'w', encoding='utf-8') as f:
    json.dump(sources, f, indent=2, ensure_ascii=False)

print('Wrote', len(sources), 'sources.')
