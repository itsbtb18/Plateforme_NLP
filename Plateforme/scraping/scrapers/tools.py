"""
NLP Tools scraper — source: HuggingFace Model Hub API.

Searches for Arabic / multilingual NLP models and maps them to the
platform's ``NLPTool`` model.
"""

import logging
from .base import BaseScraper

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
    ]

    def scrape(self):
        seen_ids = set()
        for query_params in self.QUERIES:
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

        access_url = f"https://huggingface.co/{model_id}"

        # Duplicate check
        if NLPTool.objects.filter(access_link=access_url).exists():
            self.items_skipped += 1
            return
        if NLPTool.objects.filter(title_en__iexact=title).exists():
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
        keywords = ",".join([t for t in tags if not t.startswith("arxiv:")][:8])

        try:
            NLPTool.objects.create(
                title=title,
                title_en=title,
                title_ar=title,
                description=description,
                description_en=description,
                description_ar=description,
                tool_type=tool_type,
                version="latest",
                access_link=access_url,
                documentation_link=access_url,
                supported_languages=lang,
                language="en",
                keywords=keywords,
                author=self.get_system_user(),
                approval_status="pending",
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(title, 80),
                    "type": pipeline_tag or "model",
                    "author": author,
                    "downloads": f"{downloads:,}",
                    "url": access_url,
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create tool '{title}': {exc}")
            logger.error("Failed to create NLPTool %s: %s", title, exc)
