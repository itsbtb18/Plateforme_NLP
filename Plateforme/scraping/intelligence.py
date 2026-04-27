import logging
import math
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

class ConfidenceCalculator:
    """Calculates a 0.0-1.0 confidence score for a scraped item.

    The scoring is designed to reflect real-world data quality:
    - Items with a valid title and description should start at ~70%+
    - Additional fields (dates, URLs, location) push scores higher
    - Only genuinely empty/garbage items should score below 50%
    """

    # Essential fields: if present, the item gets a high base score.
    # Optional fields: bonus points that push toward 90-100%.
    FIELD_WEIGHTS = {
        "news": {
            "title_en": 0.40,
            "description_en": 0.40,
            "url": 0.10,
            "source_url": 0.05,
            "published_date": 0.05,
        },
        "events": {
            "title_en": 0.35,
            "description_en": 0.35,
            "start_date": 0.10,
            "source_url": 0.05,
            "url": 0.05,
            "location_en": 0.05,
            "scraped_date": 0.05,
        },
        "tools": {
            "title_en": 0.40,
            "description_en": 0.35,
            "access_link": 0.10,
            "url": 0.10,
            "source_url": 0.05,
        },
        "opportunities": {
            "job_title": 0.40,
            "description": 0.35,
            "url": 0.15,
            "source_url": 0.05,
            "institution_name": 0.05,
        },
        "corpus": {
            "dataset_name": 0.40,
            "description_en": 0.40,
            "download_url": 0.10,
            "url": 0.05,
            "source_url": 0.05,
        },
        "courses": {
            "title_en": 0.40,
            "description_en": 0.40,
            "url": 0.10,
            "source_url": 0.05,
            "platform": 0.05,
        },
    }

    def calculate(self, category: str, item_data: dict) -> dict:
        weights = self.FIELD_WEIGHTS.get(category)
        if not weights:
            return {"percent": 75.0, "details": {}}

        weighted_score = 0
        details = {}
        fields_present = 0
        fields_total = len(weights)

        for field, weight in weights.items():
            val = item_data.get(field)
            score = self.score_field(val, field_name=field)
            if score > 0.1: # Threshold for "present"
                fields_present += 1
            weighted_score += weight * score
            details[field] = round(score, 2)

        # Base confidence from field weights
        raw_score = weighted_score 

        # Boost: If Title + Description are strong, the item is likely high confidence.
        # We add a small linearity boost for completeness.
        presence_ratio = fields_present / fields_total if fields_total > 0 else 0
        boost = 0.15 * presence_ratio
        
        final_score = raw_score + boost

        # Final clamping
        return {
            "percent": round(min(0.99, final_score) * 100, 1),
            "details": details,
        }

    def score_field(self, value, field_name: str = ""):
        if value is None:
            return 0

        v = str(value).strip()
        if not v or v.lower() in ("null", "none", "n/a", "[needs research]"):
            return 0

        if "date" in field_name or "deadline" in field_name:
            return self._score_date_field(v)

        if "url" in field_name or "link" in field_name:
            return self._score_url_field(v)

        if "domain" in field_name:
            return self._score_domain_field(v)

        return self._score_text_field(v)

    def _score_text_field(self, value: str) -> float:
        """Continuous text quality score to prevent hard value clustering."""
        normalized = " ".join(value.split())
        length = len(normalized)
        if length <= 2:
            return 0.2

        word_count = len(normalized.split())
        # Smooth growth curve from short snippets to rich text.
        # 30 chars ≈ 0.55, 80 chars ≈ 0.80, 200 chars ≈ 0.93
        smooth = 1.0 - math.exp(-(length / 70.0))
        score = 0.12 + (0.86 * smooth)

        # Very short one-token labels are usually weak evidence.
        if word_count <= 1 and length < 20:
            score *= 0.85

        return max(0.2, min(0.98, score))

    def _score_date_field(self, value: str) -> float:
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return 1.0
        if re.match(r"^\d{4}-\d{2}$", value):
            return 0.85
        if re.search(r"\d{4}", value):
            return 0.7
        return 0.3

    def _score_url_field(self, value: str) -> float:
        if value.startswith("https://"):
            return 1.0
        if value.startswith("http://"):
            return 0.95
        if "." in value and "/" in value:
            return 0.8
        return 0.2

    def _score_domain_field(self, value: str) -> float:
        if "." in value and len(value) >= 6:
            return 0.95
        if len(value) >= 3:
            return 0.7
        return 0.4

def calculate_item_confidence(category: str, item_data: dict) -> dict:
    calc = ConfidenceCalculator()
    return calc.calculate(category, item_data)

def compute_relevance_score(
    *,
    category: str | None = None,
    item_data: dict | None = None,
    text: str = "",
    created_date=None,
    source_health_score: float = 100.0,
    downloads: int = 0,
    citations: int = 0,
    likes: int = 0,
    has_description: bool = True,
    has_website: bool = True,
    has_arabic: bool = False,
    domain_scores: dict[str, float] | None = None,
    translation_status: str = "pending",
) -> float:
    """Compute a 0-100 relevance score for a scraped item.

    Priority order:
    1. Use the model's stored confidence_score if available.
    2. Use LLM-returned relevance_score / extraction_confidence.
    3. Fall back to field-presence-based calculation.
    """
    if isinstance(item_data, dict):
        # 1. Check for a stored confidence_score from the model
        stored_confidence = item_data.get("confidence_score")
        if stored_confidence is not None:
            try:
                numeric_score = float(stored_confidence)
                # Already on 0-100 scale from _normalize_confidence
                if 0.0 < numeric_score <= 1.0:
                    numeric_score *= 100.0
                if numeric_score > 0:
                    return round(numeric_score, 1)
            except (ValueError, TypeError):
                pass

        # 2. Use LLM-returned scores if present
        for score_key in ("relevance_score", "extraction_confidence"):
            llm_score = item_data.get(score_key)
            if llm_score is not None:
                try:
                    numeric_score = float(llm_score)
                    if 0.0 < numeric_score <= 1.0:
                        numeric_score *= 100.0
                    if numeric_score > 0:
                        return round(numeric_score, 1)
                except (ValueError, TypeError):
                    continue

    # 3. Field-presence-based calculation
    if category and isinstance(item_data, dict):
        report = calculate_item_confidence(category, item_data)
        score = float(report.get("percent", 0.0))
        return score

    # Generic fallback logic
    score = 65.0
    if has_arabic:
        score += 10
    if has_description:
        score += 10
    if has_website:
        score += 5
    return min(100.0, score)

def detect_trends(months: int = 6) -> dict:
    """Return trend datasets used by the analytics dashboard charts."""
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from .models import ScrapingRun

    cutoff = timezone.now() - timedelta(days=months * 30)

    # 1. Monthly throughput
    monthly_data = (
        ScrapingRun.objects.filter(started_at__gte=cutoff, status="completed")
        .annotate(month=TruncMonth("started_at"))
        .values("month")
        .annotate(
            count=Count("id"),
            items=Sum("items_created")
        )
        .order_by("month")
    )

    trends = []
    for row in monthly_data:
        trends.append({
            "month": row["month"].strftime("%Y-%m") if row["month"] else "?",
            "runs": row["count"],
            "items": row["items"] or 0
        })

    # 2. Growth calculation (last month vs previous)
    growth = 0.0
    if len(trends) >= 2:
        last = trends[-1]["items"]
        prev = trends[-2]["items"]
        if prev > 0:
            growth = round(((last - prev) / prev) * 100, 1)

    # 3. Top categories
    top_cats = (
        ScrapingRun.objects.filter(started_at__gte=cutoff, status="completed")
        .values("category")
        .annotate(total=Sum("items_created"))
        .order_by("-total")[:5]
    )

    top_categories = [
        {"name": row["category"], "count": row["total"] or 0}
        for row in top_cats
    ]

    return {
        "status": "ok",
        "months": months,
        "trends": trends,
        "growth": growth,
        "top_categories": top_categories,
    }

def classify_domain(text: str) -> dict[str, float]:
    """Classify the research domain of the text."""
    return {"arabic_nlp": 1.0}

def classify_domain_primary(text: str) -> str:
    """Classify the primary research domain of the text."""
    return "arabic_nlp"

def _safe_days_ago(dt) -> int:
    if not dt: return 365
    if isinstance(dt, datetime): dt = dt.date()
    delta = date.today() - dt
    return max(0, delta.days)
