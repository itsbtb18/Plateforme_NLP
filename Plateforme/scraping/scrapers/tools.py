"""
NLP Tools scraper — sources: HuggingFace Model Hub API, curated Arabic LLMs,
speech models, and HuggingFace Arabic datasets.

Searches for Arabic / multilingual NLP models and maps them to the
platform's ``NLPTool`` model.
"""

import logging
from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import (
    try_download_image,
    attach_file_to_model,
)
from scraping.field_mapping import calculate_completeness_score

logger = logging.getLogger(__name__)

# Map HuggingFace pipeline tags → NLPTool.ToolType values
PIPELINE_MAP = {
    "text-classification": "sentiment_analysis",
    "sentiment-analysis": "sentiment_analysis",
    "token-classification": "ner",
    "ner": "ner",
    "fill-mask": "tokenization",
    "text-generation": "tokenization",
    "text2text-generation": "machine_translation",
    "translation": "machine_translation",
    "summarization": "sentiment_analysis",
    "question-answering": "sentiment_analysis",
    "feature-extraction": "tokenization",
    "zero-shot-classification": "sentiment_analysis",
}

# HuggingFace language tags → NLPTool.SupportedLanguages
LANG_MAP = {
    "ar": "ar",
    "en": "en",
    "fr": "fr",
    "es": "es",
}


class ToolScraper(BaseScraper):
    """Scrape NLP tools / models from the HuggingFace Hub API."""

    name = "HuggingFace NLP Tools"
    category = "tools"

    API_BASE = "https://huggingface.co/api/models"

    # Search queries to run (each produces its own API call)
    QUERIES = [
        {"search": "arabic nlp", "limit": 15},
        {"search": "arabic text", "limit": 10},
        {"search": "camelbert", "limit": 5},
        {"search": "arbert", "limit": 5},
        {"search": "arabert", "limit": 5},
        {"search": "arabic bert", "limit": 10},
        {"search": "arabic sentiment", "limit": 5},
        {"search": "arabic ner", "limit": 5},
        {"search": "arabic speech recognition", "limit": 10},
        {"search": "arabic tts", "limit": 5},
        {"search": "arabic whisper", "limit": 5},
        {"search": "jais arabic", "limit": 5},
        {"search": "arabic llm", "limit": 10},
        {"search": "arabic summarization", "limit": 5},
    ]

    # Curated Arabic / multilingual LLM tools not easily found via search
    CURATED_LLM_TOOLS = [
        {
            "title": "Jais 13B",
            "author": "Inception / Core42",
            "pipeline_tag": "text-generation",
            "url": "https://huggingface.co/inception-mbzuai/jais-13b",
            "description": (
                "Arabic-centric bilingual (Arabic-English) large language model "
                "with 13B parameters. Trained on a large Arabic-English corpus, "
                "achieving SoTA on Arabic benchmarks."
            ),
            "tags": ["ar", "en", "text-generation", "llm"],
        },
        {
            "title": "Jais 30B Chat",
            "author": "Inception / Core42",
            "pipeline_tag": "text-generation",
            "url": "https://huggingface.co/inception-mbzuai/jais-13b-chat",
            "description": (
                "Chat-tuned version of the Jais Arabic-English bilingual LLM. "
                "Supports multi-turn conversations in Arabic and English."
            ),
            "tags": ["ar", "en", "text-generation", "llm", "chat"],
        },
        {
            "title": "AceGPT 13B Chat",
            "author": "FreedomIntelligence",
            "pipeline_tag": "text-generation",
            "url": "https://huggingface.co/FreedomIntelligence/AceGPT-13B-chat",
            "description": (
                "Arabic-focused LLM based on LLaMA, fine-tuned with Arabic "
                "instruction data and RLHF for Arabic cultural alignment."
            ),
            "tags": ["ar", "en", "text-generation", "llm"],
        },
        {
            "title": "ALLaM (Arabic Large Language Model)",
            "author": "SDAIA",
            "pipeline_tag": "text-generation",
            "url": "https://huggingface.co/sdaia",
            "description": (
                "Saudi Data and AI Authority's Arabic-first large language model "
                "for Arabic language understanding and generation tasks."
            ),
            "tags": ["ar", "text-generation", "llm"],
        },
        {
            "title": "Whisper Large V3 (Arabic fine-tuned)",
            "author": "OpenAI / Community",
            "pipeline_tag": "automatic-speech-recognition",
            "url": "https://huggingface.co/openai/whisper-large-v3",
            "description": (
                "OpenAI's Whisper large v3 with strong Arabic ASR capabilities. "
                "Community fine-tunes available for dialectal Arabic."
            ),
            "tags": ["ar", "en", "automatic-speech-recognition", "speech"],
        },
        {
            "title": "MMS (Massively Multilingual Speech) — Arabic",
            "author": "Meta / Facebook AI",
            "pipeline_tag": "automatic-speech-recognition",
            "url": "https://huggingface.co/facebook/mms-1b-all",
            "description": (
                "Meta's Massively Multilingual Speech model covering 1100+ languages "
                "including Arabic dialects. Supports ASR and TTS."
            ),
            "tags": ["ar", "automatic-speech-recognition", "multilingual"],
        },
        {
            "title": "CAMeL Tools",
            "author": "NYU Abu Dhabi CAMeL Lab",
            "pipeline_tag": "token-classification",
            "url": "https://huggingface.co/CAMeL-Lab",
            "description": (
                "Suite of Arabic NLP tools including morphological analysis, "
                "dialect identification, NER, and sentiment analysis. "
                "Built on CAMeLBERT."
            ),
            "tags": ["ar", "token-classification", "ner", "morphology"],
        },
        {
            "title": "FARASA Arabic NLP Toolkit",
            "author": "QCRI",
            "pipeline_tag": "token-classification",
            "url": "https://farasa.qcri.org",
            "description": (
                "Fast and accurate Arabic NLP toolkit by QCRI. "
                "Includes segmentation, POS tagging, NER, and diacritization."
            ),
            "tags": ["ar", "token-classification", "pos_tagging", "segmentation"],
        },
        {
            "title": "Stanza Arabic Models",
            "author": "Stanford NLP Group",
            "pipeline_tag": "token-classification",
            "url": "https://stanfordnlp.github.io/stanza/available_models.html",
            "description": (
                "Stanford Stanza's Arabic models for tokenization, POS tagging, "
                "lemmatization, dependency parsing, and NER."
            ),
            "tags": ["ar", "token-classification", "pos_tagging", "ner"],
        },
        {
            "title": "AraBERT v2",
            "author": "aubmindlab",
            "pipeline_tag": "fill-mask",
            "url": "https://huggingface.co/aubmindlab/bert-base-arabertv02",
            "description": (
                "Pre-trained Arabic BERT model. Effective for downstream Arabic NLP "
                "tasks: NER, sentiment analysis, and question answering."
            ),
            "tags": ["ar", "fill-mask", "bert", "arabic"],
        },
    ]

    # Curated HuggingFace Arabic datasets
    CURATED_DATASETS = [
        {
            "title": "Arabic Speech Corpus",
            "author": "QCRI / Dialectal Arabic",
            "url": "https://huggingface.co/datasets/arabic_speech_corpus",
            "description": (
                "High-quality Arabic speech corpus for ASR research. "
                "Contains recordings in Modern Standard Arabic."
            ),
            "tool_type": "tokenization",
            "tags": ["ar", "speech", "dataset"],
        },
        {
            "title": "HARD — Hotel Arabic Reviews Dataset",
            "author": "Community",
            "url": "https://huggingface.co/datasets/hard",
            "description": (
                "Arabic hotel review dataset for sentiment analysis. "
                "Contains 93K reviews with positive/negative labels."
            ),
            "tool_type": "sentiment_analysis",
            "tags": ["ar", "sentiment", "dataset"],
        },
        {
            "title": "ARCD — Arabic Reading Comprehension Dataset",
            "author": "Hussein Mozannar",
            "url": "https://huggingface.co/datasets/arcd",
            "description": (
                "Arabic QA dataset modeled after SQuAD. "
                "Contains 1,395 questions on Arabic Wikipedia articles."
            ),
            "tool_type": "tokenization",
            "tags": ["ar", "question-answering", "dataset"],
        },
        {
            "title": "LABR — Large-scale Arabic Book Reviews",
            "author": "Community",
            "url": "https://huggingface.co/datasets/labr",
            "description": (
                "Arabic book review dataset with 63K reviews. "
                "5-star rating scale for sentiment analysis."
            ),
            "tool_type": "sentiment_analysis",
            "tags": ["ar", "sentiment", "dataset"],
        },
        {
            "title": "WikiANN — Arabic NER",
            "author": "Pan et al.",
            "url": "https://huggingface.co/datasets/wikiann",
            "description": (
                "Cross-lingual NER dataset with Arabic split. "
                "Wikipedia-based NER tags for PER, LOC, ORG."
            ),
            "tool_type": "ner",
            "tags": ["ar", "ner", "dataset"],
        },
        {
            "title": "Calliar — Algerian Arabic Dialect Corpus",
            "author": "Community",
            "url": "https://huggingface.co/datasets/calliar",
            "description": (
                "Handwriting recognition dataset for Algerian Arabic dialect, "
                "useful for OCR and dialectal Arabic processing."
            ),
            "tool_type": "tokenization",
            "tags": ["ar", "algerian", "dialect", "dataset"],
        },
        {
            "title": "NADI — Nuanced Arabic Dialect Identification",
            "author": "NADI Shared Task",
            "url": "https://huggingface.co/datasets/nadi_2023",
            "description": (
                "Arabic dialect identification dataset covering 21 Arab countries. "
                "Includes Algerian, Egyptian, Gulf, Levantine, and Maghrebi dialects."
            ),
            "tool_type": "sentiment_analysis",
            "tags": ["ar", "dialect", "classification", "dataset"],
        },
    ]

    def scrape(self):
        try:
            from scraping.intelligence import generate_queries

            dynamic_queries = generate_queries("tools")
            hf_queries = [
                q.get("query", "") for q in dynamic_queries if q.get("query")
            ][:10]
            if not hf_queries:
                hf_queries = ["arabic nlp", "camelbert", "arabert"]
        except Exception:
            hf_queries = ["arabic nlp", "camelbert", "arabert"]

        # Build query param dicts from dynamic queries
        queries = [{"search": q, "limit": 10} for q in hf_queries]

        seen_ids = set()
        for query_params in queries:
            params = {
                "sort": "downloads",
                "direction": "-1",
                **query_params,
            }
            resp = self.safe_request(self.API_BASE, params=params)
            if resp is None:
                continue

            try:
                models = resp.json()
                if not isinstance(models, list):
                    continue

                for model in models:
                    model_id = model.get("modelId") or model.get("id", "")
                    if not model_id or model_id in seen_ids:
                        continue
                    seen_ids.add(model_id)
                    self._process_model(model)

            except Exception as exc:
                self.errors.append(f"HuggingFace parse error: {exc}")
                logger.error("HuggingFace API error: %s", exc)

        # Import curated LLM tools & speech models
        self._import_curated_llm_tools()

        # Import curated Arabic datasets
        self._import_curated_datasets()

    def _process_model(self, model: dict):
        """Create an NLPTool from a HuggingFace model dict."""
        from resources.models import NLPTool

        model_id = model.get("modelId") or model.get("id", "")
        tags = model.get("tags", [])
        pipeline_tag = model.get("pipeline_tag", "")
        downloads = model.get("downloads", 0)
        likes = model.get("likes", 0)
        author = model.get("author", "")

        # Build human-readable title
        short_name = model_id.split("/")[-1] if "/" in model_id else model_id
        title = short_name.replace("-", " ").replace("_", " ").title()
        title_en = title

        access_url = f"https://huggingface.co/{model_id}"

        # Duplicate check
        if NLPTool.objects.filter(access_link=access_url).exists():
            self.items_skipped += 1
            return
        if self.is_duplicate(title_en, "tools", NLPTool):
            self.items_skipped += 1
            return

        # Resolve tool type
        tool_type = PIPELINE_MAP.get(pipeline_tag, "tokenization")

        # Resolve supported language
        lang = "ar"  # default for our Arabic NLP focus
        for tag in tags:
            if tag in LANG_MAP:
                lang = LANG_MAP[tag]
                break

        # Build description
        description = (
            f"HuggingFace model by {author or 'community'}. "
            f"Pipeline: {pipeline_tag or 'N/A'}. "
            f"Downloads: {downloads:,}. Likes: {likes:,}. "
            f"Tags: {', '.join(tags[:10])}."
        )

        # Keywords
        keywords = [t for t in tags if not t.startswith("arxiv:")][:8]

        title_ar = title
        description_en = description
        description_ar = description
        access_link = access_url
        documentation_url = access_url
        version = "latest"
        supported_languages = [
            "arabic"
            if lang == "ar"
            else "english"
            if lang == "en"
            else "french"
            if lang == "fr"
            else "multilingual"
        ]
        primary_language = supported_languages[0]
        thumbnail_url = (
            model.get("thumbnail_url")
            or model.get("avatarUrl")
            or model.get("logo")
            or ""
        )

        item_dict = {
            "title_en": title_en,
            "title_ar": title_ar,
            "description_en": description_en,
            "description_ar": description_ar,
            "tool_type": tool_type,
            "access_link": access_link,
            "documentation_url": documentation_url,
            "version": version,
            "keywords": keywords,
            "supported_languages": supported_languages,
            "primary_language": primary_language,
            "thumbnail_url": thumbnail_url,
        }

        item_dict = enrich_scraped_item(item_dict, "tools")
        completeness = calculate_completeness_score(item_dict, "tools")

        if completeness < 40:
            self.items_skipped += 1
            return

        is_valid, item_dict, reason = self.validate_and_prepare(item_dict, "tools")
        if not is_valid:
            self.items_skipped += 1
            return

        supported_lang_map = {
            "arabic": "ar",
            "english": "en",
            "french": "fr",
            "spanish": "es",
            "multilingual": "ar",
        }
        primary_language_map = {
            "arabic": "ar",
            "english": "en",
            "french": "en",
            "bilingual": "en",
            "multilingual": "en",
        }
        supported_value = item_dict.get("supported_languages", [])
        if isinstance(supported_value, list) and supported_value:
            supported_lang = supported_lang_map.get(
                str(supported_value[0]).lower(), "ar"
            )
        else:
            supported_lang = supported_lang_map.get(str(supported_value).lower(), "ar")
        primary_lang = primary_language_map.get(
            str(item_dict.get("primary_language", "arabic")).lower(), "ar"
        )

        try:
            tool = NLPTool.objects.create(
                title=item_dict.get("title_en", "")[:200],
                title_en=item_dict.get("title_en", "")[:200],
                title_ar=item_dict.get("title_ar", "")[:200],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                tool_type=item_dict.get("tool_type", "other"),
                access_link=item_dict.get("access_link", ""),
                documentation_link=item_dict.get("documentation_url", ""),
                version=item_dict.get("version", ""),
                keywords=", ".join(
                    item_dict.get("keywords", [])
                    if isinstance(item_dict.get("keywords"), list)
                    else [item_dict.get("keywords", "")]
                ),
                supported_languages=supported_lang,
                language=primary_lang,
                approval_status="pending",
                author=self.get_system_user(),
            )

            # Try to download thumbnail/icon (non-fatal on any failure)
            thumbnail_url = (item_dict.get("thumbnail_url") or "").strip()
            if tool and getattr(tool, "pk", None) and thumbnail_url:
                try:
                    img_file, filename = try_download_image([thumbnail_url], "tools")
                    if img_file and filename:
                        attached = attach_file_to_model(
                            tool,
                            "thumbnail",
                            img_file,
                            filename,
                        )
                        if not attached:
                            logger.warning(
                                "Thumbnail attach returned False for tool=%s url=%s",
                                tool.pk,
                                thumbnail_url,
                            )
                except Exception as attach_exc:
                    logger.warning(
                        "Failed to attach thumbnail for tool=%s url=%s: %s",
                        getattr(tool, "pk", "unknown"),
                        thumbnail_url,
                        attach_exc,
                    )

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 80),
                    "type": pipeline_tag or "model",
                    "author": author,
                    "downloads": f"{downloads:,}",
                    "url": item_dict.get("access_link", access_url),
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create tool '{title}': {exc}")
            logger.error("Failed to create NLPTool %s: %s", title, exc)

    # ── Curated LLM Tools & Speech Models ────────────────────────────

    def _import_curated_llm_tools(self):
        """Import curated Arabic LLMs, speech models, and NLP toolkits."""
        from resources.models import NLPTool

        for item in self.CURATED_LLM_TOOLS:
            title = item["title"]
            title_en = title
            url = item["url"]

            if NLPTool.objects.filter(access_link=url).exists():
                self.items_skipped += 1
                continue
            if self.is_duplicate(title_en, "tools", NLPTool):
                self.items_skipped += 1
                continue

            pipeline_tag = item.get("pipeline_tag", "")
            tool_type = PIPELINE_MAP.get(pipeline_tag, "tokenization")
            tags = item.get("tags", [])
            lang = "ar"
            for tag in tags:
                if tag in LANG_MAP:
                    lang = LANG_MAP[tag]
                    break

            title_ar = title
            description_en = item["description"]
            description_ar = item["description"]
            access_link = url
            documentation_url = url
            version = "latest"
            keywords = [t for t in tags if len(t) < 30][:8]
            supported_languages = [
                "arabic"
                if lang == "ar"
                else "english"
                if lang == "en"
                else "french"
                if lang == "fr"
                else "multilingual"
            ]
            primary_language = supported_languages[0]
            thumbnail_url = item.get("thumbnail_url", "")

            item_dict = {
                "title_en": title_en,
                "title_ar": title_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "tool_type": tool_type,
                "access_link": access_link,
                "documentation_url": documentation_url,
                "version": version,
                "keywords": keywords,
                "supported_languages": supported_languages,
                "primary_language": primary_language,
                "thumbnail_url": thumbnail_url,
            }

            item_dict = enrich_scraped_item(item_dict, "tools")
            completeness = calculate_completeness_score(item_dict, "tools")

            if completeness < 40:
                self.items_skipped += 1
                continue

            is_valid, item_dict, reason = self.validate_and_prepare(item_dict, "tools")
            if not is_valid:
                self.items_skipped += 1
                continue

            supported_lang_map = {
                "arabic": "ar",
                "english": "en",
                "french": "fr",
                "spanish": "es",
                "multilingual": "ar",
            }
            primary_language_map = {
                "arabic": "ar",
                "english": "en",
                "french": "en",
                "bilingual": "en",
                "multilingual": "en",
            }
            supported_value = item_dict.get("supported_languages", [])
            if isinstance(supported_value, list) and supported_value:
                supported_lang = supported_lang_map.get(
                    str(supported_value[0]).lower(), "ar"
                )
            else:
                supported_lang = supported_lang_map.get(
                    str(supported_value).lower(), "ar"
                )
            primary_lang = primary_language_map.get(
                str(item_dict.get("primary_language", "arabic")).lower(), "ar"
            )

            try:
                tool = NLPTool.objects.create(
                    title_en=item_dict.get("title_en", "")[:200],
                    title_ar=item_dict.get("title_ar", "")[:200],
                    description_en=item_dict.get("description_en", ""),
                    description_ar=item_dict.get("description_ar", ""),
                    tool_type=item_dict.get("tool_type", "other"),
                    access_link=item_dict.get("access_link", ""),
                    documentation_link=item_dict.get("documentation_url", ""),
                    version=item_dict.get("version", ""),
                    keywords=", ".join(
                        item_dict.get("keywords", [])
                        if isinstance(item_dict.get("keywords"), list)
                        else [item_dict.get("keywords", "")]
                    ),
                    supported_languages=supported_lang,
                    language=primary_lang,
                    approval_status="pending",
                    title=item_dict.get("title_en", "")[:200],
                    description=item_dict.get("description_en", ""),
                    author=self.get_system_user(),
                )

                # Try to download thumbnail/icon (non-fatal on any failure)
                thumbnail_url = (item_dict.get("thumbnail_url") or "").strip()
                if tool and getattr(tool, "pk", None) and thumbnail_url:
                    try:
                        img_file, filename = try_download_image(
                            [thumbnail_url], "tools"
                        )
                        if img_file and filename:
                            attached = attach_file_to_model(
                                tool,
                                "thumbnail",
                                img_file,
                                filename,
                            )
                            if not attached:
                                logger.warning(
                                    "Thumbnail attach returned False for tool=%s url=%s",
                                    tool.pk,
                                    thumbnail_url,
                                )
                    except Exception as attach_exc:
                        logger.warning(
                            "Failed to attach thumbnail for tool=%s url=%s: %s",
                            getattr(tool, "pk", "unknown"),
                            thumbnail_url,
                            attach_exc,
                        )

                self.items_created += 1
                self.results.append(
                    {
                        "title": self.truncate(item_dict.get("title_en", title), 80),
                        "type": pipeline_tag or "llm",
                        "author": item.get("author", ""),
                        "downloads": "curated",
                        "url": item_dict.get("access_link", url),
                    }
                )
            except Exception as exc:
                self.errors.append(f"Failed to create curated tool '{title}': {exc}")
                logger.error("Failed to create curated NLPTool %s: %s", title, exc)

    # ── Curated Arabic Datasets ──────────────────────────────────────

    def _import_curated_datasets(self):
        """Import curated HuggingFace Arabic datasets as NLPTool entries."""
        from resources.models import NLPTool

        for item in self.CURATED_DATASETS:
            title = item["title"]
            title_en = title
            url = item["url"]

            if NLPTool.objects.filter(access_link=url).exists():
                self.items_skipped += 1
                continue
            if self.is_duplicate(title_en, "tools", NLPTool):
                self.items_skipped += 1
                continue

            tool_type = item.get("tool_type", "tokenization")
            tags = item.get("tags", [])
            title_ar = title
            description_en = f"[Dataset] {item['description']}"
            description_ar = description_en
            access_link = url
            documentation_url = url
            version = "latest"
            keywords = [t for t in tags if len(t) < 30][:8]
            supported_languages = ["arabic"]
            primary_language = "arabic"
            thumbnail_url = item.get("thumbnail_url", "")

            item_dict = {
                "title_en": title_en,
                "title_ar": title_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "tool_type": tool_type,
                "access_link": access_link,
                "documentation_url": documentation_url,
                "version": version,
                "keywords": keywords,
                "supported_languages": supported_languages,
                "primary_language": primary_language,
                "thumbnail_url": thumbnail_url,
            }

            item_dict = enrich_scraped_item(item_dict, "tools")
            completeness = calculate_completeness_score(item_dict, "tools")

            if completeness < 40:
                self.items_skipped += 1
                continue

            is_valid, item_dict, reason = self.validate_and_prepare(item_dict, "tools")
            if not is_valid:
                self.items_skipped += 1
                continue

            supported_lang_map = {
                "arabic": "ar",
                "english": "en",
                "french": "fr",
                "spanish": "es",
                "multilingual": "ar",
            }
            primary_language_map = {
                "arabic": "ar",
                "english": "en",
                "french": "en",
                "bilingual": "en",
                "multilingual": "en",
            }
            supported_value = item_dict.get("supported_languages", [])
            if isinstance(supported_value, list) and supported_value:
                supported_lang = supported_lang_map.get(
                    str(supported_value[0]).lower(), "ar"
                )
            else:
                supported_lang = supported_lang_map.get(
                    str(supported_value).lower(), "ar"
                )
            primary_lang = primary_language_map.get(
                str(item_dict.get("primary_language", "arabic")).lower(), "ar"
            )

            try:
                tool = NLPTool.objects.create(
                    title_en=item_dict.get("title_en", "")[:200],
                    title_ar=item_dict.get("title_ar", "")[:200],
                    description_en=item_dict.get("description_en", ""),
                    description_ar=item_dict.get("description_ar", ""),
                    tool_type=item_dict.get("tool_type", "other"),
                    access_link=item_dict.get("access_link", ""),
                    documentation_link=item_dict.get("documentation_url", ""),
                    version=item_dict.get("version", ""),
                    keywords=", ".join(
                        item_dict.get("keywords", [])
                        if isinstance(item_dict.get("keywords"), list)
                        else [item_dict.get("keywords", "")]
                    ),
                    supported_languages=supported_lang,
                    language=primary_lang,
                    approval_status="pending",
                    title=item_dict.get("title_en", "")[:200],
                    description=item_dict.get("description_en", ""),
                    author=self.get_system_user(),
                )

                # Try to download thumbnail/icon (non-fatal on any failure)
                thumbnail_url = (item_dict.get("thumbnail_url") or "").strip()
                if tool and getattr(tool, "pk", None) and thumbnail_url:
                    try:
                        img_file, filename = try_download_image(
                            [thumbnail_url], "tools"
                        )
                        if img_file and filename:
                            attached = attach_file_to_model(
                                tool,
                                "thumbnail",
                                img_file,
                                filename,
                            )
                            if not attached:
                                logger.warning(
                                    "Thumbnail attach returned False for tool=%s url=%s",
                                    tool.pk,
                                    thumbnail_url,
                                )
                    except Exception as attach_exc:
                        logger.warning(
                            "Failed to attach thumbnail for tool=%s url=%s: %s",
                            getattr(tool, "pk", "unknown"),
                            thumbnail_url,
                            attach_exc,
                        )

                self.items_created += 1
                self.results.append(
                    {
                        "title": self.truncate(item_dict.get("title_en", title), 80),
                        "type": "dataset",
                        "author": item.get("author", ""),
                        "downloads": "curated",
                        "url": item_dict.get("access_link", url),
                    }
                )
            except Exception as exc:
                self.errors.append(f"Failed to create dataset '{title}': {exc}")
                logger.error("Failed to create dataset NLPTool %s: %s", title, exc)
