# Plateforme Backend Installation

## Python dependencies

Install project dependencies from the backend folder:

```bash
pip install -r requirements.txt
```

## spaCy NER models

The scraping enrichment pipeline uses spaCy NER. Install at least the default English model:

```bash
python -m spacy download en_core_web_sm
```

For Arabic and multilingual extraction, install the configured Arabic model as well:

```bash
python -m spacy download xx_ent_wiki_sm
```

You can override model names with environment variables:

- `SCRAPING_SPACY_MODEL` (default: `en_core_web_sm`)
- `SCRAPING_SPACY_MODEL_AR` (default: `xx_ent_wiki_sm`)
