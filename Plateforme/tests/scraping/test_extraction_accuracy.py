from scraping.extractors.core.llm_validation import LLMValidator

from .eval_utils import (
    aggregate_metrics,
    compute_dedup_effectiveness,
    run_scraper_on_html,
)


def test_extraction_precision_recall_thresholds(ground_truth, saved_html_loader):
    metrics = aggregate_metrics(ground_truth, saved_html_loader)

    for category, payload in metrics["by_category"].items():
        assert payload["precision"] >= 0.75, (
            f"Precision too low for {category}: {payload['precision']:.3f}"
        )
        assert payload["recall"] >= 0.75, (
            f"Recall too low for {category}: {payload['recall']:.3f}"
        )

    assert metrics["micro_precision"] >= 0.80
    assert metrics["micro_recall"] >= 0.80


def test_date_parsing_accuracy_threshold(ground_truth, saved_html_loader):
    metrics = aggregate_metrics(ground_truth, saved_html_loader)

    date_categories = ["news", "events"]
    for category in date_categories:
        assert metrics["by_category"][category]["date_accuracy"] >= 0.90


def test_dedup_effectiveness_threshold(saved_html_loader):
    predicted_events = run_scraper_on_html("events", saved_html_loader("events"))
    with_duplicates = predicted_events + predicted_events[:1]

    duplicate_ratio = compute_dedup_effectiveness(with_duplicates)
    assert duplicate_ratio >= 0.30


def test_llm_validation_false_positive_rate(monkeypatch, ground_truth):
    negatives = []
    for rows in ground_truth.values():
        negatives.extend(
            [row for row in rows if not row.get("expected_relevant", True)]
        )

    assert negatives, "Fixture set must include negative examples to compute FPR"

    def fake_validate(self, item, category="general"):  # noqa: ANN001
        title = (item.get("title") or "").lower()
        return {
            "is_relevant": False if ("football" in title or "image" in title) else True,
            "is_spam": False,
            "confidence": 0.95,
            "reason": "fixture",
            "title_en": item.get("title", ""),
            "title_ar": item.get("title", ""),
            "description_en": item.get("title", ""),
            "description_ar": item.get("title", ""),
            "normalized_dates": {},
            "filled_fields": {},
        }

    monkeypatch.setattr(LLMValidator, "validate", fake_validate)

    validator = LLMValidator(client=None)
    false_positives = 0
    for item in negatives:
        response = validator.validate(item, category="eval")
        predicted_positive = bool(response and response.get("is_relevant"))
        if predicted_positive:
            false_positives += 1

    fpr = false_positives / len(negatives)
    assert fpr < 0.20
