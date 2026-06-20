"""
Elasticsearch search service — queries the Django platform's ES indices.

Mirrors the dis_max ranking logic from Django's GlobalSearchView so the
chatbot can find tools, courses, corpora, resources, events, projects,
institutions, and users, and return direct platform links.
"""

import logging
import re
from typing import Any

from app.config import get_settings
from elasticsearch import AsyncElasticsearch

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Index configuration ──────────────────────────────────────────────
# Maps ES index name → metadata required to build queries & format results.

INDEX_COURSES = "courses"
INDEX_NLP_TOOLS = "nlp_tools"
INDEX_CORPORA = "corpora"
INDEX_RESOURCES = "resources"
INDEX_PROJECTS = "projects"
INDEX_EVENTS = "events"
INDEX_INSTITUTIONS = "institutions"
INDEX_USERS = "users"

INDEX_CONFIG: dict[str, dict[str, Any]] = {
    INDEX_COURSES: {
        "type": "course",
        "url_pattern": "/resources/course/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
            "keywords",
            "keywords.english",
            "keywords.arabic",
            "keywords.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_NLP_TOOLS: {
        "type": "tool",
        "url_pattern": "/resources/tool/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
            "keywords",
            "keywords.english",
            "keywords.arabic",
            "keywords.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_CORPORA: {
        "type": "corpus",
        "url_pattern": "/resources/corpus/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
            "keywords",
            "keywords.english",
            "keywords.arabic",
            "keywords.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_RESOURCES: {
        "type": "resource",
        "url_pattern": "/resources/{document_type}/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
            "keywords",
            "keywords.english",
            "keywords.arabic",
            "keywords.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_PROJECTS: {
        "type": "project",
        "url_pattern": "/projects/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_EVENTS: {
        "type": "event",
        "url_pattern": "/events/{id}/",
        "search_fields": [
            "title",
            "title.english",
            "title.arabic",
            "title.phonetic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
        ],
        "title_field": "title",
        "description_field": "description",
    },
    INDEX_INSTITUTIONS: {
        "type": "institution",
        "url_pattern": "/institutions/{id}/",
        "search_fields": [
            "name",
            "name.english",
            "name.arabic",
            "name.phonetic",
            "acronym",
            "acronym.english",
            "acronym.arabic",
            "description",
            "description.english",
            "description.arabic",
            "description.phonetic",
        ],
        "title_field": "name",
        "description_field": "description",
    },
    INDEX_USERS: {
        "type": "user",
        "url_pattern": "/accounts/profile/{id}/",
        "search_fields": [
            "full_name",
            "full_name.english",
            "full_name.arabic",
            "full_name.phonetic",
            "bio",
            "bio.english",
            "bio.arabic",
        ],
        "title_field": "full_name",
        "description_field": "bio",
    },
}


def _detect_language(query: str) -> str:
    """Detect if query is primarily Arabic or English/other."""
    if not query:
        return "english"
    arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
    arabic_chars = len(arabic_pattern.findall(query))
    total_chars = len(query.replace(" ", ""))
    if total_chars == 0:
        return "english"
    if arabic_chars / total_chars > 0.3:
        return "arabic"
    return "english"


def _build_dis_max_query(query: str, fields: list[str], detected_lang: str) -> dict:
    """Build a dis_max query with language-aware boosting."""
    primary_suffix = (
        f".{detected_lang}" if detected_lang in ("arabic", "english") else ""
    )
    secondary_suffix = ".english" if detected_lang == "arabic" else ".arabic"

    match_clauses = []
    for field in fields:
        # Determine boost based on field type and language match
        if primary_suffix and field.endswith(primary_suffix):
            boost = 3.0
        elif field.endswith(".phonetic"):
            boost = 0.5
        elif secondary_suffix and field.endswith(secondary_suffix):
            boost = 1.0
        elif "." not in field or field.endswith(".raw"):
            boost = 2.0
        else:
            boost = 1.5

        # Title/name fields get extra boost
        base_field = field.split(".")[0]
        if base_field in ("title", "name", "full_name"):
            boost *= 1.5

        match_clauses.append({"match": {field: {"query": query, "boost": boost}}})

    return {"dis_max": {"queries": match_clauses, "tie_breaker": 0.3}}


class ElasticsearchService:
    """Async Elasticsearch search across the platform's indices."""

    def __init__(self):
        self._client: AsyncElasticsearch | None = None

    async def _get_client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(
                hosts=[settings.ELASTICSEARCH_HOST],
                request_timeout=30,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def search(
        self,
        query: str,
        *,
        indices: list[str] | None = None,
        limit_per_index: int = 5,
        total_limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search across platform ES indices and return formatted results with links.

        Args:
            query: user search text
            indices: specific indices to search (None = all)
            limit_per_index: max hits per index
            total_limit: max total results returned
        """
        client = await self._get_client()
        detected_lang = _detect_language(query)
        target_indices = indices or list(INDEX_CONFIG.keys())
        all_results: list[dict[str, Any]] = []

        for index_name in target_indices:
            config = INDEX_CONFIG.get(index_name)
            if not config:
                continue

            dis_max = _build_dis_max_query(
                query, config["search_fields"], detected_lang
            )

            try:
                response = await client.search(
                    index=index_name,
                    body={"query": dis_max, "size": limit_per_index},
                )
            except Exception as e:
                logger.warning("ES search failed for index %s: %s", index_name, e)
                continue

            hits = response.get("hits", {}).get("hits", [])
            for hit in hits:
                formatted = self._format_hit(hit, config)
                if formatted:
                    all_results.append(formatted)

        # Sort by score descending and truncate
        all_results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return all_results[:total_limit]

    @staticmethod
    def _format_hit(hit: dict, config: dict) -> dict[str, Any] | None:
        """Convert an ES hit into a flat result dict with a platform link."""
        source = hit.get("_source", {})
        doc_id = hit.get("_id")
        score = hit.get("_score", 0)
        if not doc_id:
            return None

        title_field = config["title_field"]
        desc_field = config["description_field"]

        title = source.get(title_field, "") or ""
        description = source.get(desc_field, "") or ""
        result_type = config["type"]

        # Build the platform URL
        url = config["url_pattern"].format(
            id=doc_id,
            document_type=source.get("document_type", "article"),
        )

        result: dict[str, Any] = {
            "id": doc_id,
            "type": result_type,
            "title": title[:300],
            "description": description[:300],
            "score": score,
            "url": url,
        }

        # Attach extra metadata depending on type
        extras = {
            "language": source.get("language"),
            "tool_type": source.get("tool_type"),
            "document_type": source.get("document_type"),
            "event_type": source.get("event_type"),
            "institution_type": source.get("institution_type"),
            "field": source.get("field"),
            "academic_level": source.get("academic_level"),
            "status": source.get("status"),
            "version": source.get("version"),
        }
        for k, v in extras.items():
            if v:
                result[k] = v

        # Author info
        author = source.get("author")
        if isinstance(author, dict) and author.get("full_name"):
            result["author"] = author["full_name"]

        return result


# ── Singleton ────────────────────────────────────────────────────────

_es_service: ElasticsearchService | None = None


def get_elasticsearch_service() -> ElasticsearchService:
    global _es_service
    if _es_service is None:
        _es_service = ElasticsearchService()
    return _es_service
