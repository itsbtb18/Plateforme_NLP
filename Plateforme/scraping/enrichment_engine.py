import json
import logging
import re
from collections import Counter

from scraping.field_mapping import FIELD_MAPPINGS
from scraping.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)


class EnrichmentEngine:
    """
    Automatic enrichment for scraped items.
    """

    def __init__(self):
        self.client = GroqLLMClient()

    def enrich_item(self, item, category):
        """
        Main method. Calls all sub-methods and returns enriched dict.
        """
        if not isinstance(item, dict):
            return item

        mapping = FIELD_MAPPINGS.get(category, {})
        if not mapping:
            return item

        item = dict(item)
        all_fields = {}
        all_fields.update(mapping.get("required", {}))
        all_fields.update(mapping.get("optional", {}))

        missing_fields = self._collect_missing_fields(item, all_fields)
        if not missing_fields:
            return item

        item = self._fill_translations(item, missing_fields)
        missing_fields = self._collect_missing_fields(item, all_fields)

        item = self._fill_choices_fields(item, missing_fields, category)
        missing_fields = self._collect_missing_fields(item, all_fields)

        item = self._fill_list_fields(item, missing_fields, category)

        # Fill default values for any still-missing fields.
        for field_key, config in all_fields.items():
            if (
                not self._has_meaningful_value(item.get(field_key))
                and "default" in config
            ):
                item[field_key] = config["default"]

        return item

    def _fill_translations(self, item, missing_fields):
        """
        Batch-translate all missing Arabic fields that have English source text.
        """
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

        prompt = (
            "Translate these values to Arabic. "
            "Return ONLY a valid JSON object with the exact same keys and no extra text.\n\n"
            f"{json.dumps(batch_payload, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self.client._chat(prompt)
            parsed = self._extract_json_object(response)

            for field_key, source_key, config in translation_pairs:
                translated = parsed.get(field_key)
                if self._has_meaningful_value(translated):
                    translated_text = str(translated).strip()
                    max_length = config.get("max_length")
                    if isinstance(max_length, int) and max_length > 0:
                        translated_text = translated_text[:max_length]
                    item[field_key] = translated_text
                elif not self._has_meaningful_value(item.get(field_key)):
                    # Safe fallback if translation is missing.
                    item[field_key] = item.get(source_key)
        except Exception as e:
            import logging
            logger = logging.getLogger('scraping.enrichment')
            logger.warning(
                f'Arabic translation failed: {str(e)}. '
                f'Falling back to English values. '
                f'Fields affected: '
                f'{[f for f, _, _ in translation_pairs]}'
            )
            for field_key, source_key, _config in translation_pairs:
                if not self._has_meaningful_value(item.get(field_key)):
                    item[field_key] = item.get(source_key)

        return item

    def _fill_choices_fields(self, item, missing_fields, category):
        """
        Infer missing choice fields using keyword matching and defaults.
        """
        del category  # Category is kept for extension points.

        text_blob = " ".join(
            [
                str(item.get("title_en", "")),
                str(item.get("description_en", "")),
                str(item.get("content_en", "")),
                str(item.get("name_en", "")),
                str(item.get("keywords", "")),
            ]
        ).lower()

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
        """
        Fill missing list fields: keywords, research_domains, supported_languages.
        """
        text_blob = " ".join(
            [
                str(item.get("title_en", "")),
                str(item.get("description_en", "")),
                str(item.get("content_en", "")),
                str(item.get("name_en", "")),
            ]
        )

        for field_key, config in missing_fields:
            if config.get("type") != "list":
                continue
            if self._has_meaningful_value(item.get(field_key)):
                continue

            if field_key == "keywords":
                item[field_key] = self._extract_keywords(text_blob, max_keywords=8)
                continue

            if field_key == "research_domains":
                domains = []
                try:
                    from scraping.intelligence import classify_domain

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

            # Generic fallback for any other list field.
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

    def _extract_keywords(self, text, max_keywords=8):
        """
        Simple keyword extraction: remove stopwords and return top unique words.
        """
        if not text:
            return []

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

        tokens = [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text)]
        filtered = [t for t in tokens if t not in stopwords]
        counts = Counter(filtered)

        keywords = []
        for token, _count in counts.most_common():
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= max_keywords:
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
            if min_length is not None and len(text) < int(min_length):
                return False
            return True

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
        if "french" in lowered:
            languages.append("french")

        if not languages:
            languages = ["arabic"]

        return list(dict.fromkeys(languages))


def enrich_scraped_item(item, category):
    engine = EnrichmentEngine()
    return engine.enrich_item(item, category)
