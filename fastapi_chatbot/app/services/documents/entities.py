"""
Lightweight multilingual named-entity extraction.

Phase 10: Extracts proper nouns, technical terms, numbers and
date-like tokens from chunk text.  Stored in Qdrant payload so
chunks can be boosted when the query mentions the same entity.

No external NLP model required — uses regex heuristics tuned for
Arabic, French and English academic/research text.
"""

import re
from typing import List, Set

# ---------------------------------------------------------------------------
# Compiled patterns (module-level for performance)
# ---------------------------------------------------------------------------

# English / French capitalised multi-word names (≥2 words)
_PROPER_NOUN_MULTI = re.compile(
    r"\b([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)+)\b"
)

# Single capitalised word (not start of sentence) — min 3 chars
_PROPER_NOUN_SINGLE = re.compile(
    r"(?<=[.!?]\s)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,})\b"
    r"|(?<=\n)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,})\b"
    r"|(?<=,\s)([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,})\b"
)

# Arabic proper names — words preceded by name indicators
_ARABIC_NAME_INDICATORS = re.compile(
    r"(?:الدكتور|الأستاذ|البروفيسور|السيد|الباحث|المؤلف|الكاتب)\s+"
    r"([\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+){0,3})"
)

# Acronyms (2-6 uppercase letters, optionally dotted)
_ACRONYM = re.compile(r"\b([A-Z]{2,6})\b")
_DOTTED_ACRONYM = re.compile(r"\b([A-Z]\.(?:[A-Z]\.){1,5})")

# Year-like numbers
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

# Numeric values with optional units
_NUMBER_UNIT = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*"
    r"(%|articles?|papers?|documents?|pages?|cours|outils?|tools?|MB|GB|مقال|أداة|صفحة)"
)

# Technical NLP terms (multilingual)
_NLP_TERMS = re.compile(
    r"\b("
    r"BERT|GPT|LLM|NLP|NER|POS|TF-IDF|Word2Vec|FastText|GloVe|ELMo|"
    r"Transformer|LSTM|GRU|RNN|CNN|"
    r"tokeniz(?:ation|er)|lemmatiz(?:ation|er)|stemm(?:ing|er)|"
    r"embedding|fine[- ]?tun(?:ing|ed)|"
    r"sentiment|classification|segmentation|"
    r"corpus|corpora|dataset"
    r")\b",
    re.I,
)

# Stop words to filter out (overmatched proper nouns)
_STOP_PROPER = {
    "the", "this", "that", "these", "those", "with", "from", "into",
    "les", "des", "une", "dans", "pour", "avec", "sur", "par",
    "however", "therefore", "moreover", "furthermore", "also",
    "nous", "vous", "ils", "elles", "sont", "être", "avoir",
    "has", "have", "was", "were", "been", "being", "not",
}


def extract_entities(text: str) -> List[str]:
    """Extract named entities from a text chunk.

    Returns a deduplicated, lowercased list of entity strings.
    """
    entities: Set[str] = set()

    # Multi-word proper nouns
    for m in _PROPER_NOUN_MULTI.finditer(text):
        name = m.group(1).strip()
        if len(name) > 3 and name.lower() not in _STOP_PROPER:
            entities.add(name.lower())

    # Acronyms
    for m in _ACRONYM.finditer(text):
        entities.add(m.group(1))
    for m in _DOTTED_ACRONYM.finditer(text):
        entities.add(m.group(1).replace(".", ""))

    # Arabic names
    for m in _ARABIC_NAME_INDICATORS.finditer(text):
        entities.add(m.group(1).strip())

    # NLP technical terms
    for m in _NLP_TERMS.finditer(text):
        entities.add(m.group(1).lower())

    # Years
    for m in _YEAR.finditer(text):
        entities.add(m.group(1))

    return list(entities)


def match_entities(query_entities: List[str], chunk_entities: List[str]) -> int:
    """Return the number of query entities that appear in chunk entities."""
    if not query_entities or not chunk_entities:
        return 0
    q_set = {e.lower() for e in query_entities}
    c_set = {e.lower() for e in chunk_entities}
    return len(q_set & c_set)
