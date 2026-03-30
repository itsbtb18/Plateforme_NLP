import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from scraping.scrapers.courses import CourseScraper
from scraping.scrapers.events import EventScraper
from scraping.scrapers.institutions import InstitutionScraper
from scraping.scrapers.feed import NewsScraper
from scraping.scrapers.tools import _extract_language_support, _resolve_tool_type


def _normalize_url(value: str) -> str:
    return (value or "").strip().lower().rstrip("/")


def _to_iso(value):  # noqa: ANN001
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text[:10]


def run_scraper_on_html(category: str, html: str) -> list[dict]:
    if category == "news":
        scraper = NewsScraper.__new__(NewsScraper)
        page_url = "https://example.org/news"
        urls = scraper._extract_candidate_article_links(html=html, page_url=page_url)

        soup = BeautifulSoup(html, "html.parser")
        date_map = {}
        title_map = {}
        for article in soup.select("article"):
            anchor = article.select_one("a[href]")
            if not anchor:
                continue
            url = urljoin(page_url, anchor["href"])
            title_map[_normalize_url(url)] = anchor.get_text(" ", strip=True)
            time_tag = article.select_one("time[datetime]")
            if time_tag:
                date_map[_normalize_url(url)] = (time_tag.get("datetime") or "")[:10]

        return [
            {
                "title": title_map.get(_normalize_url(url), ""),
                "url": url,
                "date": date_map.get(_normalize_url(url), ""),
            }
            for url in urls
        ]

    if category == "events":
        scraper = EventScraper.__new__(EventScraper)
        candidates = scraper._extract_event_candidates_from_html(
            html=html,
            page_url="https://events.example.org/list",
            source_name="fixture-events",
            default_location="Algiers",
            priority=1,
            tier=1,
        )
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("website", ""),
                "date": _to_iso(item.get("start_date")),
            }
            for item in candidates
        ]

    if category == "courses":
        scraper = CourseScraper.__new__(CourseScraper)
        page_url = "https://courses.example.org/catalog"
        cards = scraper._extract_catalog_cards(html, page_url)
        list_items = scraper._extract_list_items_as_courses(html, page_url)

        merged = []
        seen = set()
        for item in cards + list_items:
            url = item.get("url", "")
            key = _normalize_url(url)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "date": "",
                }
            )
        return merged

    if category == "institutions":
        scraper = InstitutionScraper.__new__(InstitutionScraper)
        cards = scraper._extract_lab_cards(
            html=html,
            page_url="https://labs.example.org/index",
        )
        return [
            {
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "date": "",
            }
            for item in cards
        ]

    if category == "tools":
        soup = BeautifulSoup(html, "html.parser")
        script = soup.select_one("script#tool-data")
        tools = json.loads(script.get_text(strip=True)) if script else []

        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "tool_type": _resolve_tool_type(item.get("pipeline_tag")),
                "languages": _extract_language_support(
                    tags=item.get("tags", []),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    card_data=item,
                ),
                "date": "",
            }
            for item in tools
        ]

    return []


def compute_precision_recall(
    predicted: list[dict], expected: list[dict]
) -> dict[str, float]:
    pred_urls = {_normalize_url(item.get("url", "")) for item in predicted}
    gt_urls = {_normalize_url(item.get("url", "")) for item in expected}

    pred_urls.discard("")
    gt_urls.discard("")

    true_positive = len(pred_urls & gt_urls)
    false_positive = len(pred_urls - gt_urls)
    false_negative = len(gt_urls - pred_urls)

    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 0.0
    )

    return {
        "tp": float(true_positive),
        "fp": float(false_positive),
        "fn": float(false_negative),
        "precision": precision,
        "recall": recall,
    }


def compute_date_accuracy(predicted: list[dict], expected: list[dict]) -> float:
    gt_date_by_url = {
        _normalize_url(item.get("url", "")): (item.get("date") or "")[:10]
        for item in expected
        if item.get("date")
    }
    if not gt_date_by_url:
        return 1.0

    pred_date_by_url = {
        _normalize_url(item.get("url", "")): (item.get("date") or "")[:10]
        for item in predicted
    }

    correct = 0
    total = 0
    for url_key, gt_date in gt_date_by_url.items():
        total += 1
        if pred_date_by_url.get(url_key, "") == gt_date:
            correct += 1

    return correct / total if total else 1.0


def compute_dedup_effectiveness(predicted: list[dict]) -> float:
    if not predicted:
        return 1.0

    all_urls = [
        _normalize_url(item.get("url", "")) for item in predicted if item.get("url")
    ]
    if not all_urls:
        return 1.0

    unique_count = len(set(all_urls))
    duplicate_count = len(all_urls) - unique_count
    return duplicate_count / len(all_urls)


def aggregate_metrics(ground_truth: dict, saved_html_loader) -> dict:  # noqa: ANN001
    by_category = {}
    total_tp = 0.0
    total_fp = 0.0
    total_fn = 0.0

    for category, expected in ground_truth.items():
        predicted = run_scraper_on_html(category, saved_html_loader(category))
        pr = compute_precision_recall(predicted, expected)
        date_accuracy = compute_date_accuracy(predicted, expected)

        by_category[category] = {
            **pr,
            "date_accuracy": date_accuracy,
            "predicted_count": len(predicted),
            "expected_count": len(expected),
        }

        total_tp += pr["tp"]
        total_fp += pr["fp"]
        total_fn += pr["fn"]

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0

    return {
        "by_category": by_category,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
    }


def render_markdown_report(metrics: dict, generated_at: str) -> str:
    lines = [
        "# Scraping Evaluation Report",
        "",
        f"Generated at: {generated_at}",
        "",
        "## Global Metrics",
        "",
        f"- Micro precision: {metrics['micro_precision']:.3f}",
        f"- Micro recall: {metrics['micro_recall']:.3f}",
        "",
        "## Per Category",
        "",
        "| Category | Precision | Recall | Date Accuracy | Predicted | Expected |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for category, payload in sorted(metrics["by_category"].items()):
        lines.append(
            "| {category} | {precision:.3f} | {recall:.3f} | {date_accuracy:.3f} | {predicted_count} | {expected_count} |".format(
                category=category,
                precision=payload["precision"],
                recall=payload["recall"],
                date_accuracy=payload["date_accuracy"],
                predicted_count=payload["predicted_count"],
                expected_count=payload["expected_count"],
            )
        )

    return "\n".join(lines) + "\n"


def write_report_file(metrics: dict, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(UTC)
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"scraping_eval_{timestamp}.md"
    content = render_markdown_report(metrics, generated_at=now_utc.isoformat())
    report_path.write_text(content, encoding="utf-8")
    return report_path
