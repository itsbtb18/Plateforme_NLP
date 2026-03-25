import re
import os

filepath = "/app/scraping/scrapers/institutions.py"  # Path in docker container
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

loader_code = """
import json
import os

def _load_curated_institutions():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'fixtures', 'curated_institutions.json'
    )
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

_institutions_data = _load_curated_institutions()

class InstitutionScraper"""

content = content.replace("class InstitutionScraper", loader_code)

content = re.sub(
    r"ALGERIAN_UNIVERSITIES = \[.*?\]",
    "ALGERIAN_UNIVERSITIES = _institutions_data.get('algerian_universities', [])",
    content,
    flags=re.DOTALL
)

content = re.sub(
    r"AFRICAN_NLP_LABS = \[.*?\]",
    "AFRICAN_NLP_LABS = _institutions_data.get('african_nlp_labs', [])",
    content,
    flags=re.DOTALL
)

content = re.sub(
    r"NORTH_AFRICAN_INSTITUTIONS = \[.*?\]",
    "NORTH_AFRICAN_INSTITUTIONS = _institutions_data.get('north_african_institutions', [])",
    content,
    flags=re.DOTALL
)

content = re.sub(
    r"ARABIC_INSTITUTIONS = \[.*?\]",
    "ARABIC_INSTITUTIONS = _institutions_data.get('arabic_institutions', [])",
    content,
    flags=re.DOTALL
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("institutions.py patched successfully.")
