from pathlib import Path

from .eval_utils import aggregate_metrics, write_report_file


def test_report_generator_writes_markdown_report(ground_truth, saved_html_loader):
    metrics = aggregate_metrics(ground_truth, saved_html_loader)
    report_path = write_report_file(metrics, reports_dir=Path("reports"))

    assert report_path.exists()
    assert report_path.name.startswith("scraping_eval_")

    content = report_path.read_text(encoding="utf-8")
    assert "# Scraping Evaluation Report" in content
    assert "## Global Metrics" in content
    assert (
        "| Category | Precision | Recall | Date Accuracy | Predicted | Expected |"
        in content
    )
