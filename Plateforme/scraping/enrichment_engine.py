import json
import logging
import os
import re
import time
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests
from django.utils import timezone

from scraping.constants import (
    ARXIV_ABS_BASE,
    GITHUB_API_BASE,
    GITHUB_API_VERSION,
    GITHUB_WEB_HOST,
    OPENALEX_API_BASE,
    ROR_WEB_BASE,
    SEMANTIC_SCHOLAR_API_BASE,
    SPACY_DEFAULT_MODEL,
    SPACY_NER_LABEL_MAP,
)
from scraping.enrichment.category_enrichers import CategoryEnrichmentMixin
from scraping.enrichment.external_apis import ExternalAPIsMixin
from scraping.enrichment.field_fillers import FieldFillerMixin
from scraping.field_mapping import FIELD_MAPPINGS
from scraping.intelligence import DOMAIN_ONTOLOGY, classify_domain
from scraping.llm_validation import GroqLLMClient
from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_FRENCH_HINTS = {
    " conférence ",
    " colloque ",
    " atelier ",
    " séminaire ",
    " en ligne ",
    " à distance ",
    " formation ",
    " institut ",
    " université ",
    " français ",
    " française ",
    " langue ",
}
_EVENT_TYPE_KEYWORDS = {
    "conference": ["conference", "colloque", "symposium", "summit"],
    "workshop": ["workshop", "atelier", "hands-on", "tutorial"],
    "seminar": ["seminar", "séminaire", "lecture", "talk", "webinar"],
    "call_for_papers": ["call for papers", "cfp", "submission", "soumission"],
    "hackathon": ["hackathon", "challenge", "competition"],
}
_ONLINE_KEYWORDS = [
    "virtual",
    "online",
    "zoom",
    "webinar",
    "en ligne",
    "a distance",
    "à distance",
    "افتراضي",
    "عبر الإنترنت",
]
_HYBRID_KEYWORDS = ["hybrid", "hybride", "مختلط"]
_LEVEL_KEYWORDS = {
    "beginner": ["introduction", "beginner", "debutant", "débutant", "مبتدئ"],
    "intermediate": ["intermediate", "intermediaire", "intermédiaire", "متوسط"],
    "advanced": ["advanced", "avance", "avancé", "متقدم", "phd"],
}


def _load_spacy_pipeline(model_name: str):
    normalized = (model_name or "").strip()
    if not normalized:
        return None
    try:
        import spacy

        nlp = spacy.load(normalized)
        logger.info("Loaded spaCy model for scraping NER: %s", normalized)
        return nlp
    except Exception as exc:
        logger.warning(
            "spaCy model unavailable model=%s error=%s. Install with: "
            "python -m spacy download %s",
            normalized,
            exc,
            normalized,
        )
        return None


_NLP = _load_spacy_pipeline(SS.SPACY_MODEL)
if _NLP is None and (SS.SPACY_MODEL or "").strip() != SPACY_DEFAULT_MODEL:
    _NLP = _load_spacy_pipeline(SPACY_DEFAULT_MODEL)

_NLP_AR = _load_spacy_pipeline(SS.SPACY_MODEL_AR)
if _NLP_AR is None:
    _NLP_AR = _NLP


def _select_spacy_pipeline(detected_language: str | None = None):
    language = (detected_language or "").strip().lower()
    if language.startswith("ar") and _NLP_AR is not None:
        return _NLP_AR
    return _NLP


def extract_named_entities(
    text: str,
    detected_language: str = "en",
) -> dict[str, list[str]]:
    """Extract normalized named entities from text using spaCy when available."""
    if not isinstance(text, str):
        return {}

    cleaned_text = text.strip()
    if not cleaned_text:
        return {}

    nlp = _select_spacy_pipeline(detected_language)
    if nlp is None:
        return {}

    max_chars = max(256, int(getattr(SS, "SPACY_MAX_CHARS", 50_000)))
    nlp_max = int(getattr(nlp, "max_length", 0) or 0)
    if nlp_max > 1:
        max_chars = min(max_chars, nlp_max - 1)

    try:
        doc = nlp(cleaned_text[:max_chars])
    except Exception as exc:
        logger.warning("spaCy NER extraction failed: %s", exc)
        return {}

    entities: dict[str, list[str]] = {
        "PERSON": [],
        "ORG": [],
        "GPE": [],
        "DATE": [],
        "TECH": [],
        "EVENT": [],
    }

    for ent in getattr(doc, "ents", []):
        raw_label = str(getattr(ent, "label_", "")).strip().upper()
        target_label = SPACY_NER_LABEL_MAP.get(raw_label)
        if not target_label:
            continue

        value = str(getattr(ent, "text", "")).strip()
        if not value:
            continue

        bucket = entities[target_label]
        if value not in bucket:
            bucket.append(value)

    return {label: values for label, values in entities.items() if values}


class EnrichmentEngine(CategoryEnrichmentMixin, FieldFillerMixin, ExternalAPIsMixin):
    """Automatic, category-aware enrichment for scraped items."""

    def __init__(self):
        self.client = None
        try:
            self.client = GroqLLMClient(
                timeout=int(max(1, SS.LLM_TIMEOUT)),
                max_retries=SS.MAX_RETRIES,
            )
        except Exception as exc:
            logger.warning(
                "LLM client init failed; continuing without LLM features: %s",
                exc,
            )
        self._http = requests.Session()

    def enrich_item(self, item: dict[str, Any], category: str) -> dict[str, Any]:
        """Run generic + category-specific enrichment and never raise to caller."""
        if not isinstance(item, dict):
            return item

        category = (category or "").strip().lower()
        mapping = FIELD_MAPPINGS.get(category, {})
        if not mapping:
            return dict(item)

        item = dict(item)
        all_fields = {}
        all_fields.update(mapping.get("required", {}))
        all_fields.update(mapping.get("optional", {}))

        expected_steps = 0
        successful_steps = 0

        try:
            missing_fields = self._collect_missing_fields(item, all_fields)
            item = self._fill_translations(item, missing_fields, category)
            missing_fields = self._collect_missing_fields(item, all_fields)
            item = self._fill_choices_fields(item, missing_fields, category)
            missing_fields = self._collect_missing_fields(item, all_fields)
            item = self._fill_list_fields(item, missing_fields, category)

            category_result = self._run_category_enrichment(item, category)
            item = category_result["item"]
            expected_steps += category_result["expected"]
            successful_steps += category_result["successful"]

            ner_blob = self._build_entity_text(item)
            if ner_blob:
                detected_language = str(item.get("language") or "").strip().lower()
                if not detected_language:
                    detected_language = self._detect_language(ner_blob)
                item["entities"] = extract_named_entities(
                    ner_blob,
                    detected_language=detected_language or "en",
                )
            else:
                item["entities"] = {}

            for field_key, config in all_fields.items():
                if (
                    not self._has_meaningful_value(item.get(field_key))
                    and "default" in config
                ):
                    item[field_key] = config["default"]

            self._persist_item_meta(
                item=item,
                category=category,
                expected_steps=expected_steps,
                successful_steps=successful_steps,
            )
            return item
        except Exception as exc:
            self._log_enrichment_failure(category, "engine", exc)
            return item

    def _run_category_enrichment(
        self, item: dict[str, Any], category: str
    ) -> dict[str, Any]:
        expected = 0
        successful = 0

        def mark(success: bool):
            nonlocal expected
            nonlocal successful
            expected += 1
            if success:
                successful += 1

        if category == "events":
            mark(self._enrich_events(item))
        elif category == "tools":
            mark(self._enrich_tools(item))
        elif category == "news":
            mark(self._enrich_news(item))
        elif category == "courses":
            mark(self._enrich_courses(item))
        elif category == "institutions":
            mark(self._enrich_institutions(item))

        return {"item": item, "expected": expected, "successful": successful}

    def _enrich_events(self, item: dict[str, Any]) -> bool:
        category = "events"
        changed = False
        ok = 0
        total = 5
        blob = self._event_text(item)

        try:
            language = self._detect_language(blob)
            if language and item.get("language") != language:
                item["language"] = language
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "language", exc)

        try:
            event_type = self._infer_event_type(item)
            if event_type and item.get("event_type") != event_type:
                item["event_type"] = event_type
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "event_type", exc)

        try:
            lowered = self._normalize_text(blob)
            is_hybrid = any(k in lowered for k in _HYBRID_KEYWORDS)
            is_online = is_hybrid or any(k in lowered for k in _ONLINE_KEYWORDS)
            if item.get("is_hybrid") is None:
                item["is_hybrid"] = bool(is_hybrid)
                changed = True
            if item.get("is_online") is None:
                item["is_online"] = bool(is_online)
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "online_hybrid", exc)

        try:
            if self._enrich_event_translations(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "title_translation", exc)

        try:
            score = self._score_event_relevance(item)
            if item.get("relevance_score") != score:
                item["relevance_score"] = score
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "relevance_score", exc)

        return changed or ok == total

    def _enrich_tools(self, item: dict[str, Any]) -> bool:
        category = "tools"
        changed = False
        ok = 0
        total = 4
        blob = self._build_text_blob(item)

        try:
            langs = set(
                item.get("supported_languages") or item.get("language_support") or []
            )
            lowered = self._normalize_text(
                blob + " " + " ".join(item.get("tags") or [])
            )
            if _ARABIC_RE.search(blob):
                langs.add("ar")
            if "darija" in lowered or " dz " in f" {lowered} ":
                langs.add("ar-dz")
            if "amazigh" in lowered or "tamazight" in lowered or "berber" in lowered:
                langs.add("ber")
            if "french" in lowered or "francais" in lowered or "français" in lowered:
                langs.add("fr")
            if "english" in lowered:
                langs.add("en")
            if not langs:
                langs = {"en"}
            normalized = sorted(langs)
            item["supported_languages"] = normalized
            item["language_support"] = normalized
            changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "language_support", exc)

        try:
            if str(item.get("tool_type", "")).strip().lower() == "other":
                inferred = self._classify_tool_type_with_llm(blob)
                if inferred and inferred != "other":
                    item["tool_type"] = inferred
                    changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "tool_type", exc)

        try:
            if self._enrich_tool_github(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "github_metadata", exc)

        try:
            if self._enrich_tool_paper_link(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "paper_url", exc)

        return changed or ok == total

    def _enrich_news(self, item: dict[str, Any]) -> bool:
        category = "news"
        changed = False
        ok = 0
        total = 5

        try:
            if self._enrich_arxiv_metadata(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "arxiv", exc)

        try:
            if self._enrich_news_citations(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "citations", exc)

        try:
            if self._boost_for_algerian_authors(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "algerian_authors", exc)

        try:
            if self._extract_news_concepts(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "concepts", exc)

        try:
            if self._generate_arabic_news_summary(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "arabic_summary", exc)

        return changed or ok == total

    def _enrich_courses(self, item: dict[str, Any]) -> bool:
        category = "courses"
        changed = False
        ok = 0
        total = 5
        blob = self._build_text_blob(item)
        lowered = self._normalize_text(blob)

        try:
            inferred = self._infer_course_level(lowered)
            if inferred:
                item["level"] = inferred
                mapped = {
                    "beginner": "bachelor",
                    "intermediate": "master",
                    "advanced": "doctorate",
                }.get(inferred, "master")
                if not self._has_meaningful_value(item.get("academic_level")):
                    item["academic_level"] = mapped
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "level", exc)

        try:
            duration = self._extract_duration(blob)
            if duration and not self._has_meaningful_value(item.get("duration")):
                item["duration"] = duration
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "duration", exc)

        try:
            language = self._detect_language(blob)
            teaching_language = {
                "ar": "arabic",
                "fr": "french",
                "en": "english",
            }.get(language, "english")
            if not self._has_meaningful_value(item.get("teaching_language")):
                item["teaching_language"] = teaching_language
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "language", exc)

        try:
            free_hit = any(w in lowered for w in ["free", "gratuit", "مجاني"])
            paid_hit = any(
                w in lowered
                for w in ["$", "€", "usd", "eur", "paid", "price", "dinar", "da"]
            )
            if item.get("is_free") is None:
                item["is_free"] = bool(free_hit and not paid_hit)
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "is_free", exc)

        try:
            topics = self._extract_topics_with_llm(blob, max_topics=SS.MAX_TOPICS)
            if topics:
                item["keywords"] = self._merge_tags(item.get("keywords"), topics)
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "topics", exc)

        return changed or ok == total

    def _enrich_institutions(self, item: dict[str, Any]) -> bool:
        category = "institutions"
        changed = False
        ok = 0
        total = 4

        try:
            desc = self._build_text_blob(item)
            domains = classify_domain(desc)
            if domains:
                ranked = [
                    k
                    for k, _v in sorted(
                        domains.items(), key=lambda x: x[1], reverse=True
                    )[:4]
                ]
                labels = [
                    DOMAIN_ONTOLOGY[d]["label_en"]
                    for d in ranked
                    if d in DOMAIN_ONTOLOGY
                ]
                if labels:
                    item["research_specialties"] = self._merge_tags(
                        item.get("research_specialties"), labels
                    )
                    changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "research_areas", exc)

        try:
            if self._enrich_institution_openalex(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "openalex", exc)

        try:
            score = self._compute_institution_nlp_score(item)
            if item.get("nlp_relevance_score") != score:
                item["nlp_relevance_score"] = score
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "nlp_relevance", exc)

        try:
            if self._enrich_institution_contact(item):
                changed = True
            ok += 1
        except Exception as exc:
            self._log_enrichment_failure(category, "contact_page", exc)

        return changed or ok == total

    def _fill_translations(self, item, missing_fields, category):
        batch_payload = {}
        translation_pairs = []

        for field_key, config in missing_fields:
            if not config.get("auto_translate"):
                continue
            if not field_key.endswith("_ar"):
                continue

            source_key = field_key[:-3] + "_en"
            source_value = item.get(source_key)
            if not self._has_meaningful_value(source_value):
                continue

            source_text = str(source_value).strip()
            max_length = config.get("max_length")
            if isinstance(max_length, int) and max_length > 0:
                source_text = source_text[:max_length]

            batch_payload[field_key] = source_text
            translation_pairs.append((field_key, source_key, config))

        if not batch_payload:
            return item

        system_prompt = (
            "You are a translation assistant for Arabic NLP data curation. "
            "Translate values from English to Arabic and return only valid JSON "
            "with exactly the same keys provided by the user."
        )
        user_prompt = (
            "Translate these values to Arabic. Return ONLY a valid JSON object "
            "with the exact same keys and no extra text.\n\n"
            f"{json.dumps(batch_payload, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self._llm_chat(system_prompt, user_prompt)
            if not response:
                raise RuntimeError("Empty response from LLM")

            parsed = self._extract_json_object(response)
            if not parsed:
                raise ValueError("LLM response did not contain a valid JSON object")

            for field_key, source_key, config in translation_pairs:
                translated = parsed.get(field_key)
                if self._has_meaningful_value(translated):
                    translated_text = str(translated).strip()
                    max_length = config.get("max_length")
                    if isinstance(max_length, int) and max_length > 0:
                        translated_text = translated_text[:max_length]
                    item[field_key] = translated_text
                elif not self._has_meaningful_value(item.get(field_key)):
                    item[field_key] = item.get(source_key)
        except Exception as exc:
            logger.warning(
                "LLM call failed source=%s category=%s exc_type=%s message=%s fields=%s",
                "EnrichmentEngine._fill_translations",
                category,
                type(exc).__name__,
                str(exc),
                [f for f, _, _ in translation_pairs],
            )
            for field_key, source_key, _config in translation_pairs:
                if not self._has_meaningful_value(item.get(field_key)):
                    item[field_key] = item.get(source_key)

        return item

    def _fill_choices_fields(self, item, missing_fields, category):
        del category
        text_blob = self._build_text_blob(item).lower()

        for field_key, config in missing_fields:
            choices = config.get("choices")
            if not choices:
                continue
            if self._has_meaningful_value(item.get(field_key)):
                continue

            inferred = self._infer_choice(field_key, text_blob, choices)
            if inferred is not None:
                item[field_key] = inferred
            elif "default" in config:
                item[field_key] = config["default"]
            elif len(choices) > 0:
                item[field_key] = choices[0]

        return item

    def _fill_list_fields(self, item, missing_fields, category):
        del category
        text_blob = self._build_text_blob(item)

        for field_key, config in missing_fields:
            if config.get("type") != "list":
                continue
            if self._has_meaningful_value(item.get(field_key)):
                continue

            if field_key == "keywords":
                item[field_key] = self._extract_keywords(
                    text_blob, max_keywords=SS.MAX_KEYWORDS
                )
                continue

            if field_key == "research_domains":
                domains = []
                try:
                    scores = classify_domain(text_blob)
                    if isinstance(scores, dict):
                        ranked = sorted(
                            scores.items(), key=lambda x: x[1], reverse=True
                        )
                        domains = [name for name, score in ranked if score >= 0.25][:3]
                except Exception as exc:
                    logger.debug("Domain classification failed: %s", exc)

                if not domains:
                    domains = ["nlp"]
                item[field_key] = domains
                continue

            if field_key == "supported_languages":
                item[field_key] = self._infer_supported_languages(text_blob)
                continue

            if "default" in config:
                default_value = config["default"]
                item[field_key] = (
                    default_value
                    if isinstance(default_value, list)
                    else [default_value]
                )
            else:
                item[field_key] = []

        return item

    def _event_text(self, item: dict[str, Any]) -> str:
        return " ".join(
            [
                str(item.get("title_en") or item.get("title") or ""),
                str(item.get("title_ar") or ""),
                str(item.get("description_en") or item.get("description") or ""),
                str(item.get("description_ar") or ""),
                str(item.get("location_en") or ""),
                str(item.get("location_ar") or ""),
            ]
        )

    def _build_text_blob(self, item: dict[str, Any]) -> str:
        parts = [
            str(item.get("title_en") or item.get("title") or ""),
            str(item.get("name_en") or item.get("name") or ""),
            str(item.get("description_en") or item.get("description") or ""),
            str(item.get("content_en") or item.get("content") or ""),
            str(item.get("keywords") or ""),
            str(item.get("tags") or ""),
            str(item.get("research_specialties") or ""),
        ]
        return " ".join(p for p in parts if p)

    def _build_entity_text(self, item: dict[str, Any]) -> str:
        keys = [
            "title",
            "title_en",
            "title_ar",
            "name",
            "name_en",
            "name_ar",
            "description",
            "description_en",
            "description_ar",
            "content",
            "content_en",
            "content_ar",
            "body",
            "body_en",
            "body_ar",
            "location",
            "location_en",
            "location_ar",
            "keywords",
            "tags",
            "authors",
            "research_specialties",
        ]
        parts: list[str] = []
        for key in keys:
            value = item.get(key)
            if isinstance(value, list):
                joined = " ".join(
                    str(v) for v in value if self._has_meaningful_value(v)
                )
                if joined:
                    parts.append(joined)
                continue
            if isinstance(value, dict):
                continue
            if self._has_meaningful_value(value):
                parts.append(str(value))
        return " ".join(parts)

    def _detect_language(self, text: str) -> str:
        normalized = f" {self._normalize_text(text)} "
        if _ARABIC_RE.search(text):
            return "ar"
        if any(k in normalized for k in _FRENCH_HINTS):
            return "fr"
        return "en"

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _infer_event_type(self, item: dict[str, Any]) -> str:
        existing = str(item.get("event_type") or "").strip().lower()
        if existing and existing != "other":
            return existing

        text = self._normalize_text(self._event_text(item))
        for event_type, terms in _EVENT_TYPE_KEYWORDS.items():
            if any(term in text for term in terms):
                return event_type

        system = (
            "Classify event type. Return only JSON with key event_type. "
            "Allowed values: conference, workshop, seminar, call_for_papers, hackathon, other."
        )
        user = json.dumps(
            {
                "title": item.get("title_en") or item.get("title"),
                "description": item.get("description_en") or item.get("description"),
            },
            ensure_ascii=False,
        )
        parsed = self._chat_json(system, user)
        llm_type = str(parsed.get("event_type") or "").strip().lower()
        return (
            llm_type
            if llm_type in set(_EVENT_TYPE_KEYWORDS.keys()) | {"other"}
            else "other"
        )

    def _enrich_event_translations(self, item: dict[str, Any]) -> bool:
        source_title = str(item.get("title_en") or item.get("title") or "").strip()
        if not source_title:
            return False

        changed = False
        lang = self._detect_language(source_title)

        if lang == "ar":
            parsed = self._chat_json(
                "Translate Arabic title to English. Return only JSON with key title_en.",
                source_title,
            )
            translated = parsed.get("title_en")
            if self._has_meaningful_value(translated):
                item["title_en"] = str(translated).strip()
                if not self._has_meaningful_value(item.get("title_ar")):
                    item["title_ar"] = source_title
                changed = True
        elif lang == "fr":
            parsed = self._chat_json(
                "Translate French title to English and Arabic. Return only JSON with keys title_en and title_ar.",
                source_title,
            )
            title_en = parsed.get("title_en")
            title_ar = parsed.get("title_ar")
            if self._has_meaningful_value(title_en):
                item["title_en"] = str(title_en).strip()
                changed = True
            if self._has_meaningful_value(title_ar):
                item["title_ar"] = str(title_ar).strip()
                changed = True

        return changed

    def _score_event_relevance(self, item: dict[str, Any]) -> int:
        text = self._normalize_text(self._event_text(item))
        score = 0
        if any(t in text for t in ["algeria", "algérie", "algerie", "الجزائر"]):
            score += 40
        if any(t in text for t in ["arabic", "arabe", "عربي"]):
            score += 25
        if any(t in text for t in ["nlp", "tal", "معالجة اللغة"]):
            score += 20
        start_date = self._parse_date_loose(item.get("start_date"))
        if start_date is None or start_date >= timezone.localdate():
            score += 15
        return max(0, min(100, int(score)))

    def _classify_tool_type_with_llm(self, text: str) -> str:
        system = (
            "Classify NLP tool type. Return only JSON with key tool_type. "
            "Allowed: tokenization, stemming, ner, pos_tagging, sentiment_analysis, machine_translation, other."
        )
        parsed = self._chat_json(system, text[:2000])
        value = str(parsed.get("tool_type") or "other").strip().lower()
        allowed = {
            "tokenization",
            "stemming",
            "ner",
            "pos_tagging",
            "sentiment_analysis",
            "machine_translation",
            "other",
        }
        return value if value in allowed else "other"

    def _enrich_tool_github(self, item: dict[str, Any]) -> bool:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        github_url = str(item.get("github_url") or "").strip()
        if not github_url:
            link = str(item.get("access_link") or "").strip()
            if f"{GITHUB_WEB_HOST}/" in link:
                github_url = link
        if not github_url or not token:
            return False

        repo_path = self._parse_github_repo(github_url)
        if not repo_path:
            return False

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        data = self._fetch_json(f"{GITHUB_API_BASE}/repos/{repo_path}", headers=headers)
        if not isinstance(data, dict):
            return False

        changed = False
        mapping = {
            "stargazers_count": "stars_count",
            "forks_count": "forks_count",
            "open_issues_count": "open_issues_count",
        }
        for src, dst in mapping.items():
            if data.get(src) is not None and item.get(dst) != data.get(src):
                item[dst] = data.get(src)
                changed = True

        pushed = data.get("pushed_at") or data.get("updated_at")
        parsed_date = self._parse_date_loose(pushed)
        if parsed_date:
            iso = parsed_date.isoformat()
            if item.get("last_updated") != iso:
                item["last_updated"] = iso
                changed = True

        license_obj = data.get("license") or {}
        license_name = license_obj.get("spdx_id") or license_obj.get("name")
        if (
            self._has_meaningful_value(license_name)
            and item.get("license") != license_name
        ):
            item["license"] = license_name
            changed = True

        topics = data.get("topics") or []
        if topics:
            item["tags"] = self._merge_tags(item.get("tags"), topics)
            item["keywords"] = self._merge_tags(item.get("keywords"), topics)
            changed = True

        return changed

    def _enrich_tool_paper_link(self, item: dict[str, Any]) -> bool:
        if self._has_meaningful_value(item.get("paper_url")):
            return False

        title = str(item.get("title_en") or item.get("title") or "").strip()
        if not title:
            return False

        data = self._fetch_json(
            f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search",
            params={
                "query": title,
                "limit": 1,
                "fields": "title,url,openAccessPdf,externalIds",
            },
        )
        candidates = (data or {}).get("data") or []
        if not candidates:
            return False
        first = candidates[0]
        paper_url = (
            ((first.get("openAccessPdf") or {}).get("url")) or first.get("url") or ""
        )
        if self._has_meaningful_value(paper_url):
            item["paper_url"] = paper_url
            return True
        return False

    def _enrich_arxiv_metadata(self, item: dict[str, Any]) -> bool:
        arxiv_id = str(item.get("arxiv_id") or "").strip()
        if not arxiv_id:
            return False

        text = self._fetch_text(f"{ARXIV_ABS_BASE}/{quote(arxiv_id)}")
        if not text:
            return False

        changed = False
        authors = re.findall(
            r'<meta\s+name="citation_author"\s+content="([^"]+)"', text
        )
        if authors:
            item["authors"] = self._merge_tags(item.get("authors"), authors)
            changed = True

        abstract_match = re.search(
            r'<meta\s+name="description"\s+content="([^"]+)"', text
        )
        if abstract_match and not self._has_meaningful_value(item.get("content_en")):
            item["content_en"] = abstract_match.group(1).strip()
            changed = True

        doi_match = re.search(r'https?://doi\.org/([^"\s<]+)', text)
        if doi_match and not self._has_meaningful_value(item.get("doi")):
            item["doi"] = doi_match.group(1)
            changed = True

        cat_match = re.search(r"Subjects:\s*</span>\s*([^<]+)</div>", text)
        if cat_match:
            categories = [c.strip() for c in cat_match.group(1).split(";") if c.strip()]
            if categories:
                item["tags"] = self._merge_tags(item.get("tags"), categories)
                changed = True

        return changed

    def _enrich_news_citations(self, item: dict[str, Any]) -> bool:
        doi = str(item.get("doi") or "").strip()
        title = str(item.get("title_en") or item.get("title") or "").strip()

        data = None
        if doi:
            encoded = quote(f"DOI:{doi}", safe=":/")
            data = self._fetch_json(
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/{encoded}",
                params={"fields": "citationCount,authors,title,abstract,url"},
            )
        if not data and title:
            search = self._fetch_json(
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search",
                params={
                    "query": title,
                    "limit": 1,
                    "fields": "citationCount,authors,title,url",
                },
            )
            entries = (search or {}).get("data") or []
            data = entries[0] if entries else None

        if not isinstance(data, dict):
            return False

        changed = False
        if data.get("citationCount") is not None and item.get(
            "citation_count"
        ) != data.get("citationCount"):
            item["citation_count"] = data.get("citationCount")
            changed = True

        authors = data.get("authors") or []
        author_names = [
            a.get("name") for a in authors if isinstance(a, dict) and a.get("name")
        ]
        if author_names:
            item["authors"] = self._merge_tags(item.get("authors"), author_names)
            changed = True

        return changed

    def _boost_for_algerian_authors(self, item: dict[str, Any]) -> bool:
        full_text = self._normalize_text(
            " ".join(
                [
                    str(item.get("authors") or ""),
                    str(item.get("content_en") or ""),
                    str(item.get("content") or ""),
                    str(item.get("source_name") or ""),
                ]
            )
        )
        if any(
            k in full_text
            for k in ["algeria", "algerian", "algerie", "algérie", "الجزائر"]
        ):
            item["relevance_score"] = 100
            return True
        return False

    def _extract_news_concepts(self, item: dict[str, Any]) -> bool:
        abstract = str(item.get("content_en") or item.get("abstract") or "").strip()
        if not abstract:
            return False
        concepts = self._extract_topics_with_llm(abstract, max_topics=SS.MAX_TOPICS)
        if concepts:
            item["tags"] = self._merge_tags(item.get("tags"), concepts)
            item["keywords"] = self._merge_tags(item.get("keywords"), concepts)
            return True
        return False

    def _generate_arabic_news_summary(self, item: dict[str, Any]) -> bool:
        abstract = str(item.get("content_en") or "").strip()
        if not abstract:
            return False

        normalized = self._normalize_text(
            abstract + " " + str(item.get("title_en") or "")
        )
        is_arabic_topic = any(
            k in normalized
            for k in ["arabic", "arabe", "العربية", "معالجة اللغة", "dialect", "darija"]
        )
        if not is_arabic_topic:
            return False

        if _ARABIC_RE.search(abstract):
            return False

        parsed = self._chat_json(
            "Summarize this English abstract in Arabic in 3-4 sentences. Return only JSON with key content_ar.",
            abstract[:3500],
        )
        content_ar = parsed.get("content_ar")
        if self._has_meaningful_value(content_ar):
            item["content_ar"] = str(content_ar).strip()
            return True
        return False

    def _infer_course_level(self, lowered: str) -> str:
        for label, keywords in _LEVEL_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                return label
        return ""

    def _extract_duration(self, text: str) -> str:
        patterns = [
            r"\b(\d{1,2})\s*(weeks?|week)\b",
            r"\b(\d{1,3})\s*(hours?|hour)\b",
            r"\b(\d{1,3})\s*(heures?|heure)\b",
            r"\b(\d{1,2})\s*(seances|séances|session|sessions)\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, self._normalize_text(text), flags=re.IGNORECASE)
            if m:
                return f"{m.group(1)} {m.group(2)}"
        return ""

    def _enrich_institution_openalex(self, item: dict[str, Any]) -> bool:
        ror_id = str(item.get("ror_id") or "").strip().replace(f"{ROR_WEB_BASE}/", "")
        if not ror_id:
            return False

        ror_uri = quote(f"{ROR_WEB_BASE}/{ror_id}", safe=":/")
        url = f"{OPENALEX_API_BASE}/{ror_uri}"
        data = self._fetch_json(url)
        if not isinstance(data, dict):
            return False

        changed = False
        works_count = data.get("works_count")
        cited_by_count = data.get("cited_by_count")
        if works_count is not None and item.get("works_count") != works_count:
            item["works_count"] = works_count
            changed = True
        if cited_by_count is not None and item.get("cited_by_count") != cited_by_count:
            item["cited_by_count"] = cited_by_count
            changed = True

        concepts = data.get("x_concepts") or []
        top_concepts = [
            c.get("display_name")
            for c in concepts[:8]
            if isinstance(c, dict) and c.get("display_name")
        ]
        if top_concepts:
            item["research_specialties"] = self._merge_tags(
                item.get("research_specialties"), top_concepts
            )
            changed = True

        return changed

    def _compute_institution_nlp_score(self, item: dict[str, Any]) -> int:
        text = self._normalize_text(
            " ".join(
                [
                    self._build_text_blob(item),
                    str(item.get("research_specialties") or ""),
                    str(item.get("x_concepts") or ""),
                ]
            )
        )
        score = 0
        if any(k in text for k in ["nlp", "natural language", "tal", "معالجة اللغة"]):
            score += 45
        if any(
            k in text
            for k in [
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "ai",
            ]
        ):
            score += 30
        if any(
            k in text
            for k in ["speech", "linguistics", "computational linguistics", "arabic"]
        ):
            score += 25
        return max(0, min(100, score))

    def _enrich_institution_contact(self, item: dict[str, Any]) -> bool:
        base = str(item.get("website") or item.get("institution_url") or "").strip()
        if not base:
            return False

        changed = False
        for suffix in ["/contact", "/about"]:
            url = urljoin(base.rstrip("/") + "/", suffix.lstrip("/"))
            text = self._fetch_text(url)
            if not text:
                continue

            email_match = re.search(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text
            )
            if email_match and not self._has_meaningful_value(item.get("email")):
                item["email"] = email_match.group(0)
                changed = True

            if not self._has_meaningful_value(item.get("director")):
                parsed = self._chat_json(
                    "Extract director or head full name from this page text. Return only JSON with key director.",
                    text[:4000],
                )
                director = parsed.get("director")
                if self._has_meaningful_value(director):
                    item["director"] = str(director).strip()
                    changed = True

        return changed

    def _extract_topics_with_llm(
        self, text: str, max_topics: int | None = None
    ) -> list[str]:
        topic_cap = max(1, int(max_topics or SS.MAX_TOPICS))
        parsed = self._chat_json(
            "Extract 3 to 5 key concepts from text. Return JSON with key topics as array of short phrases.",
            text[:4000],
        )
        topics = parsed.get("topics")
        if isinstance(topics, list):
            cleaned = [
                str(t).strip().lower() for t in topics if self._has_meaningful_value(t)
            ]
            unique = []
            for topic in cleaned:
                if topic not in unique:
                    unique.append(topic)
                if len(unique) >= topic_cap:
                    break
            return unique
        return []

    def _chat_json(self, system: str, user: str) -> dict[str, Any]:
        try:
            raw = self._llm_chat(system, user)
            if not raw:
                return {}
            parsed = self._extract_json_object(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _llm_chat(self, system: str, user: str) -> str | None:
        if self.client is None:
            return None
        try:
            return self.client._chat(system, user)
        except Exception as exc:
            logger.warning("LLM chat failed: %s", exc)
            return None

    def _retry_delay_seconds(
        self, attempt_number: int, retry_after: int | None
    ) -> float:
        if retry_after is not None and retry_after >= 0:
            delay = float(retry_after + SS.RETRY_AFTER_BUFFER)
        else:
            delay = float(SS.RETRY_BACKOFF_BASE) * (2 ** max(0, attempt_number - 1))
        return max(
            0.0,
            min(delay, float(SS.RETRY_BACKOFF_CAP), float(SS.TOTAL_TIMEOUT)),
        )

    def _parse_retry_after(self, raw_retry_after: Any) -> int | None:
        if raw_retry_after is None:
            return None
        try:
            return int(str(raw_retry_after).strip())
        except Exception:
            return None

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ):
        effective_timeout = float(timeout or SS.TOTAL_TIMEOUT)
        retries = max(0, int(SS.MAX_RETRIES))
        retryable_statuses = {429, 500, 502, 503, 504}

        for attempt in range(retries + 1):
            try:
                resp = self._http.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=effective_timeout,
                )
            except requests.RequestException:
                resp = None

            if resp is not None and (
                resp.status_code < 400 or resp.status_code not in retryable_statuses
            ):
                return resp

            if attempt >= retries:
                return resp

            retry_after = None
            if resp is not None:
                retry_after = self._parse_retry_after(resp.headers.get("Retry-After"))

            delay = self._retry_delay_seconds(attempt + 1, retry_after)
            if delay > 0:
                time.sleep(delay)

        return None

    def _fetch_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            resp = self._request_with_retry(
                "GET",
                url,
                headers=headers,
                params=params,
                timeout=SS.TOTAL_TIMEOUT,
            )
            if resp is None:
                return None
            if resp.status_code >= 400:
                return None
            return resp.json()
        except Exception:
            return None

    def _fetch_text(self, url: str) -> str:
        try:
            resp = self._request_with_retry("GET", url, timeout=SS.TOTAL_TIMEOUT)
            if resp is None:
                return ""
            if resp.status_code >= 400:
                return ""
            return resp.text or ""
        except Exception:
            return ""

    def _parse_github_repo(self, github_url: str) -> str:
        try:
            parsed = urlparse(github_url)
            if GITHUB_WEB_HOST not in parsed.netloc.lower():
                return ""
            path = parsed.path.strip("/")
            parts = [p for p in path.split("/") if p]
            if len(parts) < 2:
                return ""
            return f"{parts[0]}/{parts[1]}"
        except Exception:
            return ""

    def _parse_date_loose(self, value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if not m:
            return None
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None

    def _merge_tags(self, existing: Any, new_values: Any) -> list[str]:
        left = []
        if isinstance(existing, list):
            left = [str(v).strip() for v in existing if self._has_meaningful_value(v)]
        elif self._has_meaningful_value(existing):
            left = [str(existing).strip()]

        right = []
        if isinstance(new_values, list):
            right = [
                str(v).strip() for v in new_values if self._has_meaningful_value(v)
            ]
        elif self._has_meaningful_value(new_values):
            right = [str(new_values).strip()]

        out = []
        for value in left + right:
            if value and value not in out:
                out.append(value)
        return out

    def _persist_item_meta(
        self,
        *,
        item: dict[str, Any],
        category: str,
        expected_steps: int,
        successful_steps: int,
    ) -> None:
        try:
            from scraping.models import ScrapedItemMeta

            title = (
                item.get("title_en")
                or item.get("name_en")
                or item.get("title")
                or item.get("name")
                or "untitled"
            )
            relevance_score = float(
                item.get("relevance_score") or item.get("nlp_relevance_score") or 0.0
            )

            if expected_steps <= 0 or successful_steps <= 0:
                enrichment_status = "not_enriched"
            elif successful_steps < expected_steps:
                enrichment_status = "partial"
            else:
                enrichment_status = "complete"

            defaults = {"relevance_score": relevance_score}
            model_fields = {f.name for f in ScrapedItemMeta._meta.get_fields()}
            if "enrichment_status" in model_fields:
                defaults["enrichment_status"] = enrichment_status

            ScrapedItemMeta.objects.update_or_create(
                category=category,
                item_title=str(title)[:300],
                defaults=defaults,
            )
        except Exception as exc:
            self._log_enrichment_failure(category, "scraped_item_meta", exc)

    def _log_enrichment_failure(
        self, category: str, field: str, exc: Exception
    ) -> None:
        logger.warning(
            "enrichment failed category=%s field=%s exc_type=%s message=%s",
            category,
            field,
            type(exc).__name__,
            str(exc),
        )

    def _extract_keywords(self, text, max_keywords: int | None = None):
        if not text:
            return []

        keyword_cap = max(1, int(max_keywords or SS.MAX_KEYWORDS))

        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "into",
            "using",
            "used",
            "are",
            "was",
            "were",
            "have",
            "has",
            "had",
            "your",
            "their",
            "our",
            "about",
            "over",
            "under",
            "between",
            "through",
            "within",
            "also",
            "can",
            "could",
            "would",
            "should",
            "will",
            "may",
            "might",
            "not",
            "than",
            "then",
            "more",
            "most",
            "such",
            "some",
            "many",
            "other",
            "paper",
            "study",
            "research",
            "model",
            "models",
            "method",
            "methods",
            "approach",
            "approaches",
            "system",
            "systems",
        }

        nlp = _select_spacy_pipeline(self._detect_language(text))
        if nlp is not None:
            try:
                safe_limit = max(
                    1, min(8000, int(getattr(nlp, "max_length", 8001)) - 1)
                )
                doc = nlp(text[:safe_limit])
                entity_tokens: list[str] = []
                for ent in getattr(doc, "ents", []):
                    candidate = str(getattr(ent, "text", "")).strip().lower()
                    if not candidate:
                        continue
                    parts = [
                        p for p in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", candidate)
                    ]
                    for token in parts:
                        if token not in stopwords and token not in entity_tokens:
                            entity_tokens.append(token)
                        if len(entity_tokens) >= keyword_cap:
                            return entity_tokens
            except Exception as exc:
                logger.warning(
                    "spaCy keyword extraction failed; falling back to regex: %s",
                    exc,
                )

        tokens = [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text)]
        filtered = [t for t in tokens if t not in stopwords]
        counts = Counter(filtered)

        keywords = []
        for token, _count in counts.most_common():
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= keyword_cap:
                break

        return keywords

    def _collect_missing_fields(self, item, fields_map):
        missing = []
        for field_key, config in fields_map.items():
            if not self._has_meaningful_value(item.get(field_key), config):
                missing.append((field_key, config))
        return missing

    def _has_meaningful_value(self, value, config=None):
        if value is None:
            return False

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return False
            min_length = (config or {}).get("min_length")
            return not (min_length is not None and len(text) < int(min_length))

        if isinstance(value, (list, tuple, set)):
            return len(value) > 0

        if isinstance(value, dict):
            return len(value) > 0

        return True

    def _extract_json_object(self, text):
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}

    def _infer_choice(self, field_key, text_blob, choices):
        keyword_map = {
            "event_type": {
                "conference": ["conference", "conf", "symposium"],
                "workshop": ["workshop", "hands-on"],
                "seminar": ["seminar", "lecture", "talk", "webinar"],
                "call_for_papers": ["call for papers", "cfp", "submission"],
                "hackathon": ["hackathon", "challenge", "competition"],
            },
            "tool_type": {
                "tokenization": ["tokenization", "tokenizer", "segment"],
                "stemming": ["stem", "lemmat"],
                "ner": ["ner", "named entity", "entity recognition"],
                "pos_tagging": ["pos", "part of speech", "tagging"],
                "sentiment_analysis": ["sentiment", "emotion", "opinion"],
                "machine_translation": ["translation", "translate", "nmt", "mt"],
            },
            "field_of_study": {
                "computer_science": ["computer science", "software", "computing"],
                "linguistics": ["linguistics", "syntax", "semantics", "morphology"],
                "ai": ["ai", "artificial intelligence", "deep learning"],
                "nlp": ["nlp", "natural language", "text processing"],
                "machine_learning": ["machine learning", "supervised", "unsupervised"],
                "data_science": ["data science", "analytics", "data mining"],
                "computational_linguistics": ["computational linguistics"],
                "speech_processing": ["speech", "voice", "asr", "tts"],
            },
            "academic_level": {
                "bachelor": ["undergraduate", "bachelor", "bsc"],
                "master": ["master", "msc", "graduate"],
                "doctorate": ["phd", "doctorate", "doctoral"],
                "professional": ["professional", "certificate", "bootcamp"],
            },
            "teaching_language": {
                "arabic": ["arabic", "ar"],
                "english": ["english", "en"],
                "french": ["french", "fr"],
                "bilingual": ["bilingual", "multi-language", "multilingual"],
            },
            "institution_type": {
                "university": ["university", "college", "faculty"],
                "research_center": ["research center", "research institute", "lab"],
                "school": ["school", "academy"],
                "other": ["foundation", "organization", "institute"],
            },
            "primary_language": {
                "arabic": ["arabic", "ar"],
                "english": ["english", "en"],
                "french": ["french", "fr"],
                "multilingual": ["multilingual", "multi-language"],
            },
        }

        field_keywords = keyword_map.get(field_key, {})
        for choice in choices:
            terms = field_keywords.get(choice, [])
            for term in terms:
                if term in text_blob:
                    return choice
        return None

    def _infer_supported_languages(self, text):
        lowered = text.lower()
        languages = []

        if re.search(r"[\u0600-\u06FF]", text) or "arabic" in lowered:
            languages.append("arabic")
        if "english" in lowered or re.search(r"[a-zA-Z]", text):
            languages.append("english")
        if "french" in lowered or "francais" in lowered or "français" in lowered:
            languages.append("french")

        if not languages:
            languages = ["arabic"]

        return list(dict.fromkeys(languages))


def enrich_scraped_item(item, category):
    engine = EnrichmentEngine()
    return engine.enrich_item(item, category)
