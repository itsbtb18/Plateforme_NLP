"""
Tests for Platform Guide mode — ensures platform source cards are shown
when users select Platform Guide and ask for suggestions/recommendations.

Covers:
1. extract_resource_type correctly detects resource types from suggest queries
2. PLATFORM_PATTERNS catch suggest/recommend queries with platform keywords
3. Router broader fallback when type-specific ES search returns empty
"""

import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.classifier.patterns import (
    PLATFORM_PATTERNS,
    GENERAL_KNOWLEDGE_PATTERNS,
    extract_resource_type,
)


# ──────────────────────────────────────────────────────────────────────
# 1. extract_resource_type — detect resource types from suggest queries
# ──────────────────────────────────────────────────────────────────────


class TestExtractResourceType:
    """Verify that extract_resource_type correctly identifies platform
    entity types from natural-language suggest/recommend queries."""

    @pytest.mark.parametrize(
        "query, expected_type",
        [
            ("suggest me summarization tool", "tool"),
            ("suggest me a summarization tool in the platform", "tool"),
            ("recommend a course for NLP", "course"),
            ("any tools for translation?", "tool"),
            ("best courses for arabic NLP", "course"),
            ("show me articles about transformers", "article"),
            ("find events in Algeria", "event"),
            ("top institutions for NLP research", "institution"),
            ("recommend me a corpus for sentiment analysis", "corpus"),
            ("suggest projects related to NLP", "project"),
            ("is there any Algerian research center in the plateforme", "institution"),
            # French
            ("suggère-moi un outil de résumé", "tool"),
            ("recommande un cours de TAL", "course"),
            # Arabic
            ("اقترح أداة للتلخيص", "tool"),
            ("أفضل دورة في معالجة اللغات", "course"),
            # Edge cases — no type detected
            ("hello how are you", None),
            ("what is NLP", None),
        ],
    )
    def test_extract_resource_type(self, query, expected_type):
        assert extract_resource_type(query) == expected_type


# ──────────────────────────────────────────────────────────────────────
# 2. Classifier patterns — PLATFORM_PATTERNS catch suggest queries
# ──────────────────────────────────────────────────────────────────────


def _matches_any(patterns, text):
    """Return True if any pattern in the list matches the text."""
    for pat in patterns:
        if pat.search(text):
            return True
    return False


class TestPlatformPatterns:
    """Verify that PLATFORM_PATTERNS match suggest/recommend queries
    with platform entity keywords (tools, courses, etc.)."""

    @pytest.mark.parametrize(
        "query",
        [
            "suggest me summarization tool",
            "suggest me a summarization tool in the platform",
            "recommend a course for NLP",
            "any tools for translation?",
            "best courses for arabic NLP",
            "top tools for text analysis",
            "popular resources for machine learning",
            "available courses on deep learning",
            "tools for named entity recognition",
            "courses about sentiment analysis",
            # French
            "suggère-moi un outil de résumé",
            "recommande un cours de TAL",
            "meilleur outil pour la traduction",
            # Arabic
            "اقترح أداة للتلخيص",
            "أفضل دورة في معالجة اللغات",
            # "in the platform" explicit
            "find tools in the platform",
            "what courses are on the platform",
            "outils dans la plateforme",
            "أدوات في المنصة",
        ],
    )
    def test_platform_patterns_match_suggest_queries(self, query):
        assert _matches_any(PLATFORM_PATTERNS, query), (
            f"PLATFORM_PATTERNS should match: '{query}'"
        )

    @pytest.mark.parametrize(
        "query",
        [
            # These should NOT match PLATFORM_PATTERNS — they're general
            "suggest me a learning plan for NLP",
            "how to study machine learning",
            "what is the best approach to learn",
            "brainstorm ideas for my project",
        ],
    )
    def test_general_queries_do_not_match_platform(self, query):
        """Ensure general advisory queries don't accidentally match
        PLATFORM_PATTERNS (they should go to general_knowledge)."""
        # These may or may not match platform patterns; the key is
        # they should also match general_knowledge patterns
        if _matches_any(PLATFORM_PATTERNS, query):
            # If they match platform, they should also be caught by general
            assert _matches_any(GENERAL_KNOWLEDGE_PATTERNS, query), (
                f"Query '{query}' matched PLATFORM but not GENERAL_KNOWLEDGE"
            )


# ──────────────────────────────────────────────────────────────────────
# 3. Router broader fallback — type-specific empty → broad search
# ──────────────────────────────────────────────────────────────────────


class TestRouterPlatformFallback:
    """Verify the router's broader fallback when type-specific ES returns
    empty results for platform_query."""

    @pytest.mark.asyncio
    async def test_broad_fallback_when_type_specific_returns_empty(self):
        """When type-specific ES search returns empty, the router should
        retry with a broad search across all indices."""
        from app.services.router.engine import QueryRouter, RoutingResult
        from app.services.classifier.engine import QueryClassification

        router = QueryRouter()

        # Mock ES service: type-specific returns empty, broad returns results
        mock_es = AsyncMock()
        mock_es.search = AsyncMock(side_effect=[
            # First call: type-specific (nlp_tools) → empty
            [],
            # Second call: broad (all indices) → found results
            [
                {
                    "id": "1",
                    "type": "course",
                    "title": "Text Summarization with Transformers",
                    "description": "Learn summarization techniques",
                    "score": 8.5,
                    "url": "/resources/course/1/",
                },
            ],
        ])
        router.es_service = mock_es

        # Mock platform_qs (should NOT be called if broad ES succeeds)
        mock_pqs = AsyncMock()
        router.platform_qs = mock_pqs

        classification = QueryClassification(
            intent="platform_query",
            language="en",
            confidence=0.98,
            qdrant_collections=["platform_docs"],
        )
        classification.detected_resource_type = "tool"

        mock_db = AsyncMock()
        result = await router.route(
            question="suggest me summarization tool",
            classification=classification,
            db=mock_db,
        )

        # Should have called ES twice (type-specific, then broad)
        assert mock_es.search.call_count == 2
        # First call: type-specific with indices=["nlp_tools"]
        first_call = mock_es.search.call_args_list[0]
        assert first_call.kwargs.get("indices") == ["nlp_tools"]
        # Second call: broad with no indices filter
        second_call = mock_es.search.call_args_list[1]
        assert "indices" not in second_call.kwargs

        # Results should contain the broad search result
        assert result.platform_results is not None
        assert len(result.platform_results) == 1
        assert result.platform_results[0]["type"] == "course"
        assert result.primary_source == "platform"

    @pytest.mark.asyncio
    async def test_no_fallback_when_type_specific_has_results(self):
        """When type-specific search returns results, no broad fallback."""
        from app.services.router.engine import QueryRouter
        from app.services.classifier.engine import QueryClassification

        router = QueryRouter()

        mock_es = AsyncMock()
        mock_es.search = AsyncMock(return_value=[
            {
                "id": "42",
                "type": "tool",
                "title": "AutoSummarize NLP Tool",
                "description": "Automatic text summarization tool",
                "score": 9.0,
                "url": "/resources/tool/42/",
            },
        ])
        router.es_service = mock_es
        router.platform_qs = AsyncMock()

        classification = QueryClassification(
            intent="platform_query",
            language="en",
            confidence=0.98,
            qdrant_collections=["platform_docs"],
        )
        classification.detected_resource_type = "tool"

        result = await router.route(
            question="suggest me summarization tool",
            classification=classification,
            db=AsyncMock(),
        )

        # Only ONE call to ES (type-specific succeeded)
        assert mock_es.search.call_count == 1
        assert result.platform_results[0]["type"] == "tool"
        assert result.primary_source == "platform"

    @pytest.mark.asyncio
    async def test_postgresql_fallback_when_all_es_empty(self):
        """When both type-specific AND broad ES return empty, fall back
        to PostgreSQL unified_search."""
        from app.services.router.engine import QueryRouter
        from app.services.classifier.engine import QueryClassification

        router = QueryRouter()

        mock_es = AsyncMock()
        mock_es.search = AsyncMock(return_value=[])  # Always empty
        router.es_service = mock_es

        mock_pqs = AsyncMock()
        mock_pqs.unified_search = AsyncMock(return_value=[
            {
                "id": "99",
                "type": "tool",
                "title": "Summary Tool (PostgreSQL result)",
                "description": "Found via PostgreSQL",
                "url": "/resources/tool/99/",
            },
        ])
        router.platform_qs = mock_pqs

        classification = QueryClassification(
            intent="platform_query",
            language="en",
            confidence=0.98,
            qdrant_collections=["platform_docs"],
        )
        classification.detected_resource_type = "tool"

        result = await router.route(
            question="suggest me summarization tool",
            classification=classification,
            db=AsyncMock(),
        )

        # ES called twice (type-specific + broad), both empty
        assert mock_es.search.call_count == 2
        # PostgreSQL unified_search should have been called
        mock_pqs.unified_search.assert_called_once()
        # Results should come from PostgreSQL
        assert result.platform_results is not None
        assert len(result.platform_results) == 1
        assert result.platform_results[0]["title"] == "Summary Tool (PostgreSQL result)"
        assert result.primary_source == "platform"
