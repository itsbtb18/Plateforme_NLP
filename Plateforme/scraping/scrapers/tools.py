"""
NLP Tools scraper — sources: HuggingFace Model Hub API, curated Arabic LLMs,
speech models, and HuggingFace Arabic datasets.

Searches for Arabic / multilingual NLP models and maps them to the
platform's ``NLPTool`` model.
"""

import logging
import re
from datetime import datetime
from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import (
    attach_file_to_model,
)
from scraping.field_mapping import calculate_completeness_score

logger = logging.getLogger(__name__)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _extract_repo_path(github_url):
    if not github_url:
        return ""
    match = re.search(r"github\.com/([^/]+/[^/#?]+)", github_url)
    if not match:
        return ""
    return match.group(1).strip()


# Canonical HuggingFace task -> internal tool_type mapping.
HF_TASK_TO_TOOL_TYPE = {
    "text-generation": "language_model",
    "text2text-generation": "language_model",
    "fill-mask": "language_model",
    "token-classification": "ner_pos_tool",
    "text-classification": "text_classification",
    "question-answering": "qa_tool",
    "summarization": "summarization_tool",
    "translation": "translation_tool",
    "sentence-similarity": "embedding_model",
    "feature-extraction": "embedding_model",
    "automatic-speech-recognition": "speech_tool",
    "text-to-speech": "speech_tool",
    "image-to-text": "multimodal_tool",
    "visual-question-answering": "multimodal_tool",
    "zero-shot-classification": "text_classification",
    "conversational": "language_model",
    "table-question-answering": "qa_tool",
    "multiple-choice": "qa_tool",
    "object-detection": "vision_tool",
    "image-classification": "vision_tool",
}


def _resolve_tool_type(task_name):
    return HF_TASK_TO_TOOL_TYPE.get((task_name or "").strip().lower(), "other_nlp_tool")


def _extract_language_support(*, tags=None, title="", description="", card_data=None):
    values = []
    if isinstance(tags, list):
        values.extend(str(t) for t in tags if t)
    if isinstance(card_data, dict):
        card_langs = card_data.get("language")
        if isinstance(card_langs, list):
            values.extend(str(v) for v in card_langs if v)
        elif card_langs:
            values.append(str(card_langs))
    values.append(title or "")
    values.append(description or "")

    blob = " ".join(values).lower()
    support = []
    if any(token in blob for token in ["arabic", " arab ", "ar", "darija", "maghrebi"]):
        support.append("ar")
    if "multilingual" in blob or "multi-lingual" in blob:
        support.append("multilingual")
    if any(token in blob for token in ["french", "francais", "français", " fr "]):
        support.append("fr")
    return sorted(set(support))


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
    DATASET_API_BASE = "https://huggingface.co/api/datasets"

    def run(self) -> dict:
        logger.info(
            "scraper_run_config",
            extra={
                "category": self.category,
                "source_name": self.name,
                "media_download_enabled": self._is_download_enabled(),
            },
        )
        return super().run()

    TIER_1_GITHUB_ORGS = [
        "ESI-Algiers",
        "USTHB",
    ]

    TIER_1_GITHUB_SEARCH_QUERIES = [
        "arabic nlp algeria stars:>2",
        "darija nlp stars:>2",
        "amazigh nlp stars:>2",
        "org:ESI-Algiers arabic nlp",
        "org:USTHB arabic nlp",
    ]

    TIER_1_HF_DATASET_QUERIES = [
        "dz",
        "algeria",
        "algerian",
        "darija",
        "amazigh",
        "tamazight",
    ]

    TIER_1_RSS_SOURCES = [
        ("https://www.esi.dz", "ESI Algiers"),
        ("https://www.usthb.dz", "USTHB"),
    ]

    TIER_2_HF_ARABIC_QUERIES = [
        "arabic dialect",
        "darija",
        "egyptian arabic",
        "gulf arabic",
        "classical arabic",
        "fusha",
        "arabic ner",
        "arabic sentiment",
        "arabic summarization",
        "arabic asr",
        "arabic translation",
    ]

    TIER_2_RSS_SOURCES = [
        ("https://camel.abudhabi.nyu.edu", "CAMeL Lab"),
        ("https://farasa.qcri.org", "Farasa"),
        ("https://www.hbku.edu.qa/en/qcri", "QCRI"),
    ]

    TIER_2_KNOWN_GITHUB_TOOLS = [
        {
            "repo": "CAMeL-Lab/camel_tools",
            "source_name": "CAMeL Tools",
            "paper_url": "https://aclanthology.org/2020.lrec-1.868/",
            "demo_url": "https://camel.abudhabi.nyu.edu/",
        },
        {
            "repo": "qcri/Farasa",
            "source_name": "Farasa Toolkit",
            "paper_url": "https://aclanthology.org/L16-1170/",
            "demo_url": "https://farasa.qcri.org",
        },
        {
            "repo": "linuxscout/mishkal",
            "source_name": "Mishkal",
            "paper_url": "",
            "demo_url": "",
        },
        {
            "repo": "linuxscout/pyarabic",
            "source_name": "PyArabic",
            "paper_url": "",
            "demo_url": "",
        },
    ]

    PAPERSWITHCODE_METHODS_API = (
        "https://paperswithcode.com/api/v1/methods/?format=json"
    )

    HF_ALGERIAN_FIRST_QUERIES = [
        "Arabic NLP Algeria",
        "Algerian dialect Arabic",
        "Maghrebi Arabic NLP",
        "darija NLP",
    ]

    HF_GENERAL_ARABIC_QUERIES = [
        "arabic nlp",
        "arabic text",
        "camelbert",
        "arabert",
        "arabic bert",
        "arabic sentiment",
        "arabic ner",
        "arabic speech recognition",
        "arabic tts",
        "arabic whisper",
    ]

    HF_GLOBAL_NLP_QUERIES = [
        "jais arabic",
        "arabic llm",
        "arabic summarization",
        "nlp model",
    ]

    TIER_3_RSS_SOURCES = [
        ("https://huggingface.co/blog", "Hugging Face Blog"),
        ("https://paperswithcode.com", "PapersWithCode"),
        ("https://www.masakhane.io", "Masakhane"),
    ]

    GITHUB_QUERIES = [
        "arabic nlp algeria stars:>5",
        "arabic nlp language:python stars:>10",
        "darija nlp",
        "arabic speech recognition",
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
            "github_url": "https://github.com/CAMeL-Lab/camel_tools",
            "demo_url": "https://camel.abudhabi.nyu.edu/",
            "paper_url": "https://aclanthology.org/2020.lrec-1.868/",
            "license": "MIT",
            "author_organization": "CAMeL Lab",
            "source_name": "Curated Arabic Tools",
            "source_url": "https://huggingface.co/CAMeL-Lab",
            "installation_instructions": "pip install camel-tools",
            "use_cases": ["morphology", "ner", "dialect_identification"],
            "language_support": ["ar"],
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
            "github_url": "https://github.com/QCRI/Farasa",
            "demo_url": "https://farasa.qcri.org/",
            "paper_url": "https://aclanthology.org/L16-1170/",
            "license": "Research",
            "author_organization": "QCRI",
            "source_name": "Curated Arabic Tools",
            "source_url": "https://farasa.qcri.org",
            "installation_instructions": "Use Farasa web API or downloadable toolkit from official site",
            "use_cases": ["segmentation", "pos_tagging", "ner"],
            "language_support": ["ar"],
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
            "github_url": "https://github.com/aub-mind/arabert",
            "paper_url": "https://aclanthology.org/2020.osact-1.2/",
            "license": "Apache-2.0",
            "author_organization": "AUB Mind Lab",
            "source_name": "Curated Arabic Tools",
            "source_url": "https://huggingface.co/aubmindlab/bert-base-arabertv02",
            "installation_instructions": "pip install transformers; load with AutoModel from HuggingFace",
            "use_cases": ["classification", "qa", "ner"],
            "language_support": ["ar"],
        },
        {
            "title": "AraGPT2",
            "author": "aubmindlab",
            "pipeline_tag": "text-generation",
            "url": "https://huggingface.co/aubmindlab/aragpt2-base",
            "description": (
                "Arabic GPT-2 model for natural language generation in Modern Standard "
                "Arabic and dialectal variants."
            ),
            "tags": ["ar", "text-generation", "gpt2", "arabic"],
            "github_url": "https://github.com/aub-mind/arabert",
            "paper_url": "https://arxiv.org/abs/2012.15520",
            "license": "Apache-2.0",
            "author_organization": "AUB Mind Lab",
            "source_name": "Curated Arabic Tools",
            "source_url": "https://huggingface.co/aubmindlab/aragpt2-base",
            "installation_instructions": "pip install transformers; use AutoModelForCausalLM with aragpt2",
            "use_cases": ["generation", "chat", "summarization"],
            "language_support": ["ar"],
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
        self._seen_hf_model_ids = set()
        self._seen_hf_dataset_ids = set()

        # Tier 1: Algerian/North-African sources first.
        self._scrape_tier_1_tools()

        # Tier 2: Arabic NLP ecosystem sources.
        self._scrape_tier_2_tools()

        # Tier 3: Global sources after Tier 1 and Tier 2.
        self._scrape_tier_3_tools()

    def _scrape_tier_1_tools(self):
        self._import_tools_from_rss_sources(self.TIER_1_RSS_SOURCES)
        self._import_algerian_github_orgs()
        self._import_tier_1_github_searches()
        self._import_tier_1_hf_datasets()

    def _scrape_tier_2_tools(self):
        self._import_tools_from_rss_sources(self.TIER_2_RSS_SOURCES)
        self._import_hf_models_for_queries(
            self.TIER_2_HF_ARABIC_QUERIES,
            source_name="HuggingFace Arabic Ecosystem",
        )
        self._import_known_github_tools()
        self._import_madamira_tool()
        self._import_curated_llm_tools()
        self._import_curated_datasets()

    def _scrape_tier_3_tools(self):
        self._import_tools_from_rss_sources(self.TIER_3_RSS_SOURCES)
        try:
            from scraping.intelligence import generate_queries

            dynamic_queries = generate_queries("tools")
            dynamic_hf_queries = [
                q.get("query", "") for q in dynamic_queries if q.get("query")
            ][:10]
            if not dynamic_hf_queries:
                dynamic_hf_queries = ["arabic nlp", "camelbert", "arabert"]
        except Exception:
            dynamic_hf_queries = ["arabic nlp", "camelbert", "arabert"]

        ordered_query_terms = []
        for bucket in [self.HF_GLOBAL_NLP_QUERIES, dynamic_hf_queries]:
            for term in bucket:
                if term and term not in ordered_query_terms:
                    ordered_query_terms.append(term)

        self._import_hf_models_for_queries(
            ordered_query_terms,
            source_name="HuggingFace Global Models",
        )

        # Add GitHub repositories for broader Arabic NLP tools.
        self._import_github_tools()

        # Global sources requested.
        self._import_paperswithcode_methods()
        self._import_masakhane_tools()

    def _import_tools_from_rss_sources(self, sources):
        rss = self.get_rss_scraper()
        for base_url, source_name in sources:
            for feed_url in rss.auto_discover_feeds(base_url):
                items = rss.parse_feed_items(feed_url, max_items=40)
                for item in items:
                    self._import_tool_from_rss_item(
                        item,
                        source_name=source_name,
                        source_url=feed_url,
                    )

    def _import_tool_from_rss_item(self, item: dict, source_name: str, source_url: str):
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        url = str(item.get("url") or "").strip()
        blob = f"{title} {description} {url}".lower()

        if not any(
            token in blob
            for token in (
                "nlp",
                "natural language",
                "language model",
                "arabic",
                "darija",
                "ai",
                "machine learning",
                "speech",
            )
        ):
            return

        repo_path = self._extract_github_repo_path_from_text(
            url
        ) or self._extract_github_repo_path_from_text(description)
        if not repo_path:
            return

        resp = self.safe_request(
            f"https://api.github.com/repos/{repo_path}",
            headers={"Accept": "application/vnd.github+json"},
            source_name=f"RSS {source_name}",
        )
        if resp is None:
            return

        try:
            repo = resp.json()
        except Exception:
            return
        if not isinstance(repo, dict):
            return

        self._process_github_repo(
            repo,
            source_query=f"rss:{source_name}",
            extra_metadata={
                "source_name": f"RSS {source_name}",
                "source_url": source_url,
            },
        )

    @staticmethod
    def _extract_github_repo_path_from_text(value: str) -> str:
        if not value:
            return ""
        match = re.search(r"github\.com/([^\s/]+/[^\s/#?]+)", value)
        if not match:
            return ""
        return match.group(1).strip().rstrip("/")

    def _import_hf_models_for_queries(self, query_terms, source_name="HuggingFace"):
        for query in query_terms:
            params = {
                "sort": "downloads",
                "direction": "-1",
                "search": query,
                "limit": 15,
            }
            resp = self.safe_request(
                self.API_BASE, params=params, source_name=source_name
            )
            if resp is None:
                continue

            try:
                models = resp.json()
                if not isinstance(models, list):
                    continue

                for model in models:
                    model_id = model.get("modelId") or model.get("id", "")
                    if not model_id or model_id in self._seen_hf_model_ids:
                        continue
                    self._seen_hf_model_ids.add(model_id)
                    self._process_model(model)
            except Exception as exc:
                self.errors.append(f"HuggingFace parse error ({query}): {exc}")
                logger.error("HuggingFace API error query=%s err=%s", query, exc)

        # Import curated LLM tools & speech models
        self._import_curated_llm_tools()

        # Import curated Arabic datasets
        self._import_curated_datasets()

    def _import_github_tools(self):
        """Search GitHub repositories and import Arabic NLP tools metadata."""
        for query in self.GITHUB_QUERIES:
            resp = self.safe_request(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 20},
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp is None:
                continue

            try:
                payload = resp.json()
                repos = payload.get("items", []) if isinstance(payload, dict) else []
                for repo in repos:
                    self._process_github_repo(repo, source_query=query)
            except Exception as exc:
                self.errors.append(f"GitHub parse error for '{query}': {exc}")
                logger.error("GitHub API parse error (%s): %s", query, exc)

    def _import_algerian_github_orgs(self):
        for org in self.TIER_1_GITHUB_ORGS:
            resp = self.safe_request(
                f"https://api.github.com/orgs/{org}/repos",
                params={"sort": "updated", "per_page": 100},
                headers={"Accept": "application/vnd.github+json"},
                source_name=f"GitHub Org {org}",
            )
            if resp is None:
                continue

            try:
                repos = resp.json()
                if not isinstance(repos, list):
                    continue
                for repo in repos:
                    blob = " ".join(
                        [
                            str(repo.get("name", "")),
                            str(repo.get("description", "")),
                            " ".join(repo.get("topics", []))
                            if isinstance(repo.get("topics"), list)
                            else "",
                        ]
                    ).lower()
                    if not any(
                        term in blob
                        for term in ["nlp", "arabic", "darija", "amazigh", "language"]
                    ):
                        continue
                    self._process_github_repo(
                        repo,
                        source_query=f"org:{org}",
                        extra_metadata={"source_name": f"GitHub Org {org}"},
                    )
            except Exception as exc:
                self.errors.append(f"GitHub org parse error for '{org}': {exc}")

    def _import_tier_1_github_searches(self):
        for query in self.TIER_1_GITHUB_SEARCH_QUERIES:
            resp = self.safe_request(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
                headers={"Accept": "application/vnd.github+json"},
                source_name="GitHub Search Tier1",
            )
            if resp is None:
                continue
            try:
                payload = resp.json()
                repos = payload.get("items", []) if isinstance(payload, dict) else []
                for repo in repos:
                    self._process_github_repo(
                        repo,
                        source_query=query,
                        extra_metadata={"source_name": "GitHub Search Tier1"},
                    )
            except Exception as exc:
                self.errors.append(f"Tier1 GitHub search parse error '{query}': {exc}")

    def _import_tier_1_hf_datasets(self):
        for query in self.TIER_1_HF_DATASET_QUERIES:
            resp = self.safe_request(
                self.DATASET_API_BASE,
                params={"search": query, "limit": 30},
                source_name="HuggingFace Datasets Tier1",
            )
            if resp is None:
                continue

            try:
                datasets = resp.json()
                if not isinstance(datasets, list):
                    continue
                for dataset in datasets:
                    ds_id = dataset.get("id", "")
                    if not ds_id or ds_id in self._seen_hf_dataset_ids:
                        continue
                    self._seen_hf_dataset_ids.add(ds_id)
                    self._process_hf_dataset(dataset, source_query=query)
            except Exception as exc:
                self.errors.append(f"HF dataset parse error '{query}': {exc}")

    def _process_hf_dataset(self, dataset: dict, source_query: str):
        from resources.models import NLPTool

        dataset_id = dataset.get("id", "")
        if not dataset_id:
            return

        title = dataset_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
        title_en = title
        access_link = f"https://huggingface.co/datasets/{dataset_id}"

        media_seed = self._download_media(
            {
                "title_en": title_en,
                "source_url": access_link,
                "access_link": access_link,
                "thumbnail_url": "",
                "documentation_pdf_url": access_link,
            },
            "tools",
        )

        card_data = dataset.get("cardData") or {}
        tags = dataset.get("tags", []) if isinstance(dataset.get("tags"), list) else []
        description = (
            card_data.get("dataset_info", {}).get("description")
            if isinstance(card_data.get("dataset_info"), dict)
            else ""
        )
        if not description:
            description = (
                dataset.get("description") or f"HuggingFace dataset: {dataset_id}"
            )

        is_duplicate, _ = self._check_duplicate_policy(
            "tools",
            {
                "title_en": title_en,
                "access_link": access_link,
                "github_url": "",
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return

        language_support = _extract_language_support(
            tags=tags,
            title=title,
            description=description,
            card_data=card_data,
        )
        if not language_support:
            language_support = ["ar"]

        supported_languages = [
            "arabic"
            if "ar" in language_support
            else "french"
            if "fr" in language_support
            else "multilingual"
            if "multilingual" in language_support
            else "english"
        ]

        item_dict = {
            "title_en": title_en,
            "title_ar": title,
            "description_en": f"[Dataset] {description}",
            "description_ar": f"[Dataset] {description}",
            "tool_type": "tokenization",
            "access_link": access_link,
            "documentation_url": access_link,
            "github_url": "",
            "source_url": f"{self.DATASET_API_BASE}?search={source_query}",
            "source_name": "HuggingFace Datasets",
            "version": "latest",
            "keywords": tags[:8],
            "supported_languages": supported_languages,
            "primary_language": "arabic" if "ar" in language_support else "english",
            "use_cases": ["dataset"],
            "language_support": language_support,
            "image_local_path": media_seed.get("image_local_path") or "",
            "image_content_file": media_seed.get("image_content_file"),
            "pdf_local_path": media_seed.get("pdf_local_path") or "",
            "pdf_content_file": media_seed.get("pdf_content_file"),
        }

        item_dict = enrich_scraped_item(item_dict, "tools")
        completeness = calculate_completeness_score(item_dict, "tools")
        if completeness < 40:
            self.items_skipped += 1
            return

        is_valid, item_dict, _ = self.validate_and_prepare(item_dict, "tools")
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
        supported_value = item_dict.get("supported_languages", [])
        if isinstance(supported_value, list) and supported_value:
            supported_lang = supported_lang_map.get(
                str(supported_value[0]).lower(), "ar"
            )
        else:
            supported_lang = supported_lang_map.get(str(supported_value).lower(), "ar")

        try:
            tool = NLPTool.objects.create(
                title=item_dict.get("title_en", "")[:200],
                title_en=item_dict.get("title_en", "")[:200],
                title_ar=item_dict.get("title_ar", "")[:200],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                tool_type=item_dict.get("tool_type", "other_nlp_tool"),
                access_link=item_dict.get("access_link", ""),
                documentation_link=item_dict.get("documentation_url", ""),
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
                version=item_dict.get("version", ""),
                keywords=", ".join(item_dict.get("keywords", []))
                if isinstance(item_dict.get("keywords"), list)
                else str(item_dict.get("keywords", "")),
                supported_languages=supported_lang,
                language="ar" if supported_lang == "ar" else "en",
                use_cases=item_dict.get("use_cases") or None,
                approval_status="pending",
                author=self.get_system_user(),
            )

            self._attach_tool_media(tool, item_dict, title)
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 80),
                    "type": "dataset",
                    "author": "HuggingFace",
                    "downloads": "dataset",
                    "url": item_dict.get("access_link", access_link),
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create HF dataset '{title}': {exc}")

    def _import_known_github_tools(self):
        for entry in self.TIER_2_KNOWN_GITHUB_TOOLS:
            repo_path = entry.get("repo", "")
            if not repo_path:
                continue

            resp = self.safe_request(
                f"https://api.github.com/repos/{repo_path}",
                headers={"Accept": "application/vnd.github+json"},
                source_name=entry.get("source_name") or repo_path,
            )
            if resp is None:
                continue

            try:
                repo = resp.json()
                if not isinstance(repo, dict):
                    continue
                self._process_github_repo(
                    repo,
                    source_query=repo_path,
                    extra_metadata={
                        "paper_url": entry.get("paper_url") or None,
                        "demo_url": entry.get("demo_url") or None,
                        "source_name": entry.get("source_name")
                        or "Arabic NLP Ecosystem",
                    },
                )
            except Exception as exc:
                self.errors.append(f"Known tool repo parse error '{repo_path}': {exc}")

    def _import_madamira_tool(self):
        madamira_url = "https://camel.abudhabi.nyu.edu/madamira/"
        resp = self.safe_request(madamira_url, source_name="MADAMIRA")
        if resp is None:
            return

        try:
            soup = None
            try:
                from bs4 import BeautifulSoup as _BS

                soup = _BS(resp.text, "html.parser")
            except Exception:
                soup = None

            title = "MADAMIRA"
            description = "MADAMIRA is an Arabic morphological analysis and disambiguation toolkit."
            if soup is not None:
                if soup.title and soup.title.text:
                    title = soup.title.text.strip()[:200] or title
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    description = meta_desc.get("content").strip()[:1200]

            self._process_github_repo(
                {
                    "name": title,
                    "html_url": madamira_url,
                    "description": description,
                    "topics": ["arabic", "morphology", "nlp", "madamira"],
                    "stargazers_count": None,
                    "license": None,
                    "updated_at": None,
                    "owner": {"login": "Columbia/LDC"},
                    "homepage": madamira_url,
                },
                source_query="MADAMIRA docs",
                extra_metadata={
                    "source_name": "MADAMIRA",
                    "paper_url": "",
                },
            )
        except Exception as exc:
            self.errors.append(f"MADAMIRA metadata parse error: {exc}")

    def _import_paperswithcode_methods(self):
        resp = self.safe_request(
            self.PAPERSWITHCODE_METHODS_API,
            source_name="PapersWithCode",
        )
        if resp is None:
            return

        try:
            payload = resp.json()
            methods = payload.get("results", []) if isinstance(payload, dict) else []
            for method in methods[:60]:
                name = method.get("name") or method.get("full_name")
                if not name:
                    continue

                title = str(name).strip()
                description = (
                    method.get("description") or ""
                ).strip() or f"Method from PapersWithCode: {title}"
                paper_url = ""
                paper_obj = method.get("paper")
                if isinstance(paper_obj, dict):
                    paper_url = (
                        paper_obj.get("url_pdf") or paper_obj.get("url_abs") or ""
                    )

                self._process_github_repo(
                    {
                        "name": title,
                        "html_url": method.get("url_abs")
                        or method.get("url")
                        or self.PAPERSWITHCODE_METHODS_API,
                        "description": description,
                        "topics": ["nlp", "method", "paperswithcode"],
                        "owner": {"login": "PapersWithCode"},
                    },
                    source_query="PapersWithCode methods",
                    extra_metadata={
                        "paper_url": paper_url or None,
                        "source_name": "PapersWithCode",
                    },
                )
        except Exception as exc:
            self.errors.append(f"PapersWithCode parse error: {exc}")

    def _import_masakhane_tools(self):
        resp = self.safe_request(
            "https://api.github.com/orgs/masakhane-io/repos",
            params={"sort": "updated", "per_page": 100},
            headers={"Accept": "application/vnd.github+json"},
            source_name="Masakhane",
        )
        if resp is None:
            return

        try:
            repos = resp.json()
            if not isinstance(repos, list):
                return
            for repo in repos:
                self._process_github_repo(
                    repo,
                    source_query="org:masakhane-io",
                    extra_metadata={"source_name": "Masakhane"},
                )
        except Exception as exc:
            self.errors.append(f"Masakhane repo parse error: {exc}")

    def _process_github_repo(self, repo: dict, source_query: str, extra_metadata=None):
        from resources.models import NLPTool

        extra_metadata = extra_metadata or {}

        github_url = repo.get("html_url", "")
        name = repo.get("name", "")
        if not github_url or not name:
            return

        title = name.replace("-", " ").replace("_", " ").title()
        title_en = title

        media_seed = self._download_media(
            {
                "title_en": title_en,
                "source_url": extra_metadata.get("source_url")
                or "https://api.github.com/search/repositories",
                "access_link": github_url,
                "github_url": github_url,
                "thumbnail_url": "",
            },
            "tools",
        )

        is_duplicate, _ = self._check_duplicate_policy(
            "tools",
            {
                "title_en": title_en,
                "access_link": github_url,
                "github_url": github_url,
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return

        description = repo.get("description") or "Arabic NLP repository from GitHub."
        tags = repo.get("topics", []) if isinstance(repo.get("topics"), list) else []
        task_guess_blob = f"{title} {description} {' '.join(tags)}".lower()
        pipeline_guess = ""
        if "translation" in task_guess_blob:
            pipeline_guess = "translation"
        elif "question answering" in task_guess_blob or "qa" in task_guess_blob:
            pipeline_guess = "question-answering"
        elif "speech" in task_guess_blob or "asr" in task_guess_blob:
            pipeline_guess = "automatic-speech-recognition"
        elif "embedding" in task_guess_blob:
            pipeline_guess = "feature-extraction"
        elif "classification" in task_guess_blob:
            pipeline_guess = "text-classification"
        elif "generation" in task_guess_blob or "llm" in task_guess_blob:
            pipeline_guess = "text-generation"

        language_support = _extract_language_support(
            tags=tags,
            title=title,
            description=description,
            card_data={"language": repo.get("language")},
        )
        if not language_support:
            language_support = ["ar"]

        supported_languages = [
            "arabic"
            if "ar" in language_support
            else "french"
            if "fr" in language_support
            else "multilingual"
            if "multilingual" in language_support
            else "english"
        ]

        item_dict = {
            "title_en": title_en,
            "title_ar": title,
            "description_en": description,
            "description_ar": description,
            "tool_type": _resolve_tool_type(pipeline_guess),
            "access_link": github_url,
            "documentation_url": extra_metadata.get("documentation_url")
            or repo.get("homepage")
            or github_url,
            "github_url": github_url,
            "demo_url": extra_metadata.get("demo_url") or repo.get("homepage") or None,
            "paper_url": extra_metadata.get("paper_url") or None,
            "license": extra_metadata.get("license")
            or (
                (repo.get("license") or {}).get("name")
                if isinstance(repo.get("license"), dict)
                else None
            ),
            "stars_count": repo.get("stargazers_count"),
            "last_updated": _parse_date(repo.get("updated_at")),
            "installation_instructions": extra_metadata.get("installation_instructions")
            or None,
            "use_cases": tags[:6] or None,
            "author_organization": (repo.get("owner") or {}).get("login")
            if isinstance(repo.get("owner"), dict)
            else None,
            "source_url": extra_metadata.get("source_url")
            or "https://api.github.com/search/repositories",
            "source_name": extra_metadata.get("source_name")
            or f"GitHub Search ({source_query})",
            "version": "latest",
            "keywords": tags[:8],
            "supported_languages": supported_languages,
            "primary_language": "arabic" if "ar" in language_support else "english",
            "thumbnail_url": "",
            "image_local_path": media_seed.get("image_local_path") or "",
            "image_content_file": media_seed.get("image_content_file"),
            "pdf_local_path": media_seed.get("pdf_local_path") or "",
            "pdf_content_file": media_seed.get("pdf_content_file"),
            "language_support": language_support,
        }

        item_dict = enrich_scraped_item(item_dict, "tools")
        completeness = calculate_completeness_score(item_dict, "tools")
        if completeness < 40:
            self.items_skipped += 1
            return

        is_valid, item_dict, _ = self.validate_and_prepare(item_dict, "tools")
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
                tool_type=item_dict.get("tool_type", "other_nlp_tool"),
                access_link=item_dict.get("access_link", ""),
                documentation_link=item_dict.get("documentation_url", ""),
                github_url=item_dict.get("github_url", "") or None,
                demo_url=item_dict.get("demo_url") or None,
                paper_url=item_dict.get("paper_url") or None,
                license=item_dict.get("license") or None,
                stars_count=item_dict.get("stars_count"),
                last_updated=item_dict.get("last_updated"),
                installation_instructions=item_dict.get("installation_instructions")
                or None,
                use_cases=item_dict.get("use_cases") or None,
                author_organization=item_dict.get("author_organization") or None,
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
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

            self._attach_tool_media(tool, item_dict, title)
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(item_dict.get("title_en", title), 80),
                    "type": item_dict.get("tool_type", "other_nlp_tool"),
                    "author": item_dict.get("author_organization", ""),
                    "downloads": "github",
                    "url": item_dict.get("github_url", github_url),
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create GitHub tool '{title}': {exc}")
            logger.error("Failed to create GitHub NLPTool %s: %s", title, exc)

    def _fetch_github_stars(self, github_url: str):
        repo_path = _extract_repo_path(github_url)
        if not repo_path:
            return None
        resp = self.safe_request(f"https://api.github.com/repos/{repo_path}")
        if resp is None:
            return None
        try:
            payload = resp.json()
            stars = payload.get("stargazers_count")
            if isinstance(stars, int):
                return stars
        except Exception:
            return None
        return None

    def _attach_tool_media(self, tool, item_dict: dict, title: str):
        if not tool or not getattr(tool, "pk", None):
            return
        image_local_path = (item_dict.get("image_local_path") or "").strip()
        if image_local_path:
            try:
                attach_file_to_model(
                    tool,
                    "thumbnail",
                    item_dict.get("image_content_file"),
                    image_local_path,
                )
            except Exception as attach_exc:
                logger.warning(
                    "Failed to attach thumbnail for tool=%s title=%s: %s",
                    getattr(tool, "pk", "unknown"),
                    title,
                    attach_exc,
                )

    def _process_model(self, model: dict):
        """Create an NLPTool from a HuggingFace model dict."""
        from resources.models import NLPTool

        model_id = model.get("modelId") or model.get("id", "")
        tags = model.get("tags", [])
        pipeline_tag = model.get("pipeline_tag", "")
        downloads = model.get("downloads", 0)
        likes = model.get("likes", 0)
        author = model.get("author", "")
        card_data = model.get("cardData") or {}

        # Build human-readable title
        short_name = model_id.split("/")[-1] if "/" in model_id else model_id
        title = short_name.replace("-", " ").replace("_", " ").title()
        title_en = title

        access_url = f"https://huggingface.co/{model_id}"

        # Resolve tool type
        tool_type = _resolve_tool_type(pipeline_tag)

        # Build description
        description = (
            f"HuggingFace model by {author or 'community'}. "
            f"Pipeline: {pipeline_tag or 'N/A'}. "
            f"Downloads: {downloads:,}. Likes: {likes:,}. "
            f"Tags: {', '.join(tags[:10])}."
        )

        language_support = _extract_language_support(
            tags=tags,
            title=title,
            description=description,
            card_data=card_data,
        )
        if not language_support:
            language_support = ["ar"]

        # Keywords
        keywords = [t for t in tags if not t.startswith("arxiv:")][:8]

        github_url = (
            model.get("github_url")
            or card_data.get("github")
            or card_data.get("repository")
            or ""
        )
        demo_url = card_data.get("demo") or card_data.get("demo_url") or ""
        paper_url = card_data.get("paper") or card_data.get("paper_url") or ""
        license_value = model.get("license") or card_data.get("license") or ""
        stars_count = self._fetch_github_stars(github_url) if github_url else None
        last_updated = _parse_date(
            model.get("lastModified") or card_data.get("updated_at")
        )
        installation_instructions = card_data.get("installation") or None
        use_cases = [
            t
            for t in tags
            if t
            in [
                "translation",
                "summarization",
                "text-classification",
                "token-classification",
                "question-answering",
            ]
        ]
        source_url = f"https://huggingface.co/{model_id}"
        source_name = "HuggingFace"

        title_ar = title
        description_en = description
        description_ar = description
        access_link = access_url
        documentation_url = access_url
        version = "latest"
        supported_languages = [
            "arabic"
            if "ar" in language_support
            else "french"
            if "fr" in language_support
            else "multilingual"
            if "multilingual" in language_support
            else "english"
        ]
        primary_language = (
            "arabic" if "ar" in language_support else supported_languages[0]
        )
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
            "github_url": github_url,
            "demo_url": demo_url,
            "paper_url": paper_url,
            "license": license_value,
            "stars_count": stars_count,
            "last_updated": last_updated,
            "installation_instructions": installation_instructions,
            "use_cases": use_cases or None,
            "author_organization": author or None,
            "source_url": source_url,
            "source_name": source_name,
            "version": version,
            "keywords": keywords,
            "supported_languages": supported_languages,
            "primary_language": primary_language,
            "thumbnail_url": thumbnail_url,
            "language_support": language_support,
        }

        item_dict = self._download_media(item_dict, "tools")

        is_duplicate, _ = self._check_duplicate_policy(
            "tools",
            {
                "title_en": title_en,
                "access_link": access_url,
                "github_url": model.get("github_url", ""),
            },
        )
        if is_duplicate:
            self.items_skipped += 1
            return

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
                github_url=item_dict.get("github_url", "") or None,
                demo_url=item_dict.get("demo_url") or None,
                paper_url=item_dict.get("paper_url") or None,
                license=item_dict.get("license") or None,
                stars_count=item_dict.get("stars_count"),
                last_updated=item_dict.get("last_updated"),
                installation_instructions=item_dict.get("installation_instructions")
                or None,
                use_cases=item_dict.get("use_cases") or None,
                author_organization=item_dict.get("author_organization") or None,
                source_url=item_dict.get("source_url") or None,
                source_name=item_dict.get("source_name") or None,
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

            self._attach_tool_media(tool, item_dict, title)

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

            pipeline_tag = item.get("pipeline_tag", "")
            tool_type = _resolve_tool_type(pipeline_tag)
            tags = item.get("tags", [])
            language_support = item.get(
                "language_support"
            ) or _extract_language_support(
                tags=tags,
                title=title,
                description=item.get("description", ""),
                card_data=None,
            )
            if not language_support:
                language_support = ["ar"]

            title_ar = title
            description_en = item["description"]
            description_ar = item["description"]
            access_link = url
            documentation_url = url
            version = "latest"
            keywords = [t for t in tags if len(t) < 30][:8]
            supported_languages = [
                "arabic"
                if "ar" in language_support
                else "french"
                if "fr" in language_support
                else "multilingual"
                if "multilingual" in language_support
                else "english"
            ]
            primary_language = (
                "arabic" if "ar" in language_support else supported_languages[0]
            )
            thumbnail_url = item.get("thumbnail_url", "")

            item_dict = {
                "title_en": title_en,
                "title_ar": title_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "tool_type": tool_type,
                "access_link": access_link,
                "documentation_url": documentation_url,
                "github_url": item.get("github_url", ""),
                "demo_url": item.get("demo_url") or None,
                "paper_url": item.get("paper_url") or None,
                "license": item.get("license") or None,
                "stars_count": self._fetch_github_stars(item.get("github_url", "")),
                "last_updated": _parse_date(item.get("last_updated")),
                "installation_instructions": item.get("installation_instructions")
                or None,
                "use_cases": item.get("use_cases") or None,
                "author_organization": item.get("author") or None,
                "source_url": item.get("source_url") or item.get("url") or None,
                "source_name": item.get("source_name") or "Curated LLM Tools",
                "version": version,
                "keywords": keywords,
                "supported_languages": supported_languages,
                "primary_language": primary_language,
                "thumbnail_url": thumbnail_url,
                "language_support": language_support,
            }

            item_dict = self._download_media(item_dict, "tools")

            is_duplicate, _ = self._check_duplicate_policy(
                "tools",
                {
                    "title_en": title_en,
                    "access_link": url,
                    "github_url": item.get("github_url", ""),
                },
            )
            if is_duplicate:
                self.items_skipped += 1
                continue

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
                    github_url=item_dict.get("github_url", "") or None,
                    demo_url=item_dict.get("demo_url") or None,
                    paper_url=item_dict.get("paper_url") or None,
                    license=item_dict.get("license") or None,
                    stars_count=item_dict.get("stars_count"),
                    last_updated=item_dict.get("last_updated"),
                    installation_instructions=item_dict.get("installation_instructions")
                    or None,
                    use_cases=item_dict.get("use_cases") or None,
                    author_organization=item_dict.get("author_organization") or None,
                    source_url=item_dict.get("source_url") or None,
                    source_name=item_dict.get("source_name") or None,
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

                self._attach_tool_media(tool, item_dict, title)

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

            tool_type = item.get("tool_type", "other_nlp_tool")
            tags = item.get("tags", [])
            title_ar = title
            description_en = f"[Dataset] {item['description']}"
            description_ar = description_en
            access_link = url
            documentation_url = url
            version = "latest"
            keywords = [t for t in tags if len(t) < 30][:8]
            language_support = item.get(
                "language_support"
            ) or _extract_language_support(
                tags=tags,
                title=title,
                description=item.get("description", ""),
                card_data=None,
            )
            if not language_support:
                language_support = ["ar"]
            supported_languages = [
                "arabic"
                if "ar" in language_support
                else "french"
                if "fr" in language_support
                else "multilingual"
                if "multilingual" in language_support
                else "english"
            ]
            primary_language = (
                "arabic" if "ar" in language_support else supported_languages[0]
            )
            thumbnail_url = item.get("thumbnail_url", "")

            item_dict = {
                "title_en": title_en,
                "title_ar": title_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "tool_type": tool_type,
                "access_link": access_link,
                "documentation_url": documentation_url,
                "github_url": item.get("github_url", ""),
                "demo_url": item.get("demo_url") or None,
                "paper_url": item.get("paper_url") or None,
                "license": item.get("license") or None,
                "stars_count": self._fetch_github_stars(item.get("github_url", "")),
                "last_updated": _parse_date(item.get("last_updated")),
                "installation_instructions": item.get("installation_instructions")
                or None,
                "use_cases": item.get("use_cases") or ["dataset"],
                "author_organization": item.get("author") or None,
                "source_url": item.get("source_url") or item.get("url") or None,
                "source_name": item.get("source_name") or "Curated Datasets",
                "version": version,
                "keywords": keywords,
                "supported_languages": supported_languages,
                "primary_language": primary_language,
                "thumbnail_url": thumbnail_url,
                "language_support": language_support,
            }

            item_dict = self._download_media(item_dict, "tools")

            is_duplicate, _ = self._check_duplicate_policy(
                "tools",
                {
                    "title_en": title_en,
                    "access_link": url,
                    "github_url": item.get("github_url", ""),
                },
            )
            if is_duplicate:
                self.items_skipped += 1
                continue

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
                    github_url=item_dict.get("github_url", "") or None,
                    demo_url=item_dict.get("demo_url") or None,
                    paper_url=item_dict.get("paper_url") or None,
                    license=item_dict.get("license") or None,
                    stars_count=item_dict.get("stars_count"),
                    last_updated=item_dict.get("last_updated"),
                    installation_instructions=item_dict.get("installation_instructions")
                    or None,
                    use_cases=item_dict.get("use_cases") or None,
                    author_organization=item_dict.get("author_organization") or None,
                    source_url=item_dict.get("source_url") or None,
                    source_name=item_dict.get("source_name") or None,
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

                self._attach_tool_media(tool, item_dict, title)

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
