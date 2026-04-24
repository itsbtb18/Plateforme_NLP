from scraping.intelligence import ConfidenceCalculator, compute_relevance_score


def _news_payload(
    title: str,
    description: str,
    *,
    url: str = "https://example.com/a",
    source_url: str = "https://source.example.com/a",
    published_date: str = "2026-04-24",
) -> dict:
    return {
        "title_en": title,
        "description_en": description,
        "url": url,
        "source_url": source_url,
        "published_date": published_date,
    }


def test_news_confidence_varies_with_content_quality():
    calc = ConfidenceCalculator()

    weak = calc.calculate(
        "news",
        _news_payload(
            title="NLP",
            description="Short note.",
            url="example.com/news",
            source_url="source.example.com",
            published_date="2026",
        ),
    )["percent"]

    strong = calc.calculate(
        "news",
        _news_payload(
            title="Arabic NLP Workshop 2026",
            description=(
                "This article summarizes a new Arabic NLP workshop covering"
                " evaluation benchmarks, shared tasks, and reproducible methods"
                " for transformer-based models."
            ),
        ),
    )["percent"]

    assert strong > weak
    assert strong - weak >= 8.0


def test_text_scoring_is_not_flat_high_bucket():
    calc = ConfidenceCalculator()

    medium = calc.score_field("A" * 85, "description_en")
    long = calc.score_field("B" * 230, "description_en")

    assert long > medium
    assert (long - medium) > 0.01


def test_compute_relevance_score_prefers_existing_confidence_score():
    score = compute_relevance_score(
        category="news",
        item_data={
            "confidence_score": 82.5,
            "title_en": "Title",
            "description_en": "Desc",
        },
    )

    assert score == 82.5
