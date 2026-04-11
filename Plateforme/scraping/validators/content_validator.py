import logging
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


_CATEGORY_KEYWORDS = {
    "events": {
        "conference",
        "workshop",
        "seminar",
        "symposium",
        "call for papers",
        "cfp",
        "summit",
        "hackathon",
        "nlp",
        "ai",
    },
    "tools": {
        "tool",
        "model",
        "dataset",
        "library",
        "huggingface",
        "github",
        "tokenization",
        "translation",
        "speech",
        "nlp",
    },
    "courses": {
        "course",
        "curriculum",
        "syllabus",
        "lesson",
        "lecture",
        "training",
        "certificate",
        "mooc",
        "nlp",
        "ai",
    },
}


class ExtractionQualityValidator:
    MIN_CONFIDENCE_TO_SAVE = 0.40
    MIN_TITLE_LENGTH = 5
    MAX_TITLE_LENGTH = 300

    def validate(self, item: dict, category: str) -> tuple[bool, list[str]]:
        del category
        errors: list[str] = []
        warnings: list[str] = []

        title_en = str(item.get("title_en") or "").strip()
        if not title_en or len(title_en) < self.MIN_TITLE_LENGTH:
            errors.append("title_en too short or missing")
        if len(title_en) > self.MAX_TITLE_LENGTH:
            warnings.append(
                f"title_en too long: {len(title_en)} > {self.MAX_TITLE_LENGTH}"
            )

        url = str(
            item.get("url") or item.get("download_url") or item.get("source_url") or ""
        ).strip()
        if not url or not url.startswith(("http://", "https://")):
            errors.append(f"Invalid URL: {url}")

        title_ar = str(item.get("title_ar") or "").strip()
        if title_ar and title_ar == title_en:
            warnings.append("title_ar is copy of title_en - translation needed")
            item["translation_status"] = "copied"
        elif title_ar:
            arabic_chars = sum(1 for c in title_ar if "\u0600" <= c <= "\u06ff")
            if arabic_chars > len(title_ar) * 0.3:
                item["translation_status"] = "translated"
            else:
                item["translation_status"] = "copied"
        else:
            item["translation_status"] = "missing"

        if not item.get("is_arabic_nlp_relevant", True):
            try:
                relevance_score = float(item.get("relevance_score", 1.0))
            except (TypeError, ValueError):
                relevance_score = 1.0
            if relevance_score < 0.3:
                errors.append("Item not relevant to Arabic NLP")

        try:
            confidence = float(item.get("extraction_confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < self.MIN_CONFIDENCE_TO_SAVE:
            errors.append(
                f"Confidence too low: {confidence} < {self.MIN_CONFIDENCE_TO_SAVE}"
            )

        is_valid = len(errors) == 0
        return is_valid, errors + warnings


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str):
        text = (data or "").strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return " ".join(self._parts)


class ContentValidator:
    """Keyword-based content relevance validator built on stdlib parsing."""

    MAX_BYTES = 250_000

    def __init__(self, url: str, category: str):
        self.url = (url or "").strip()
        self.category = (category or "").strip().lower()

    def run(self) -> dict:
        if not self.url:
            raise ValueError("URL is required")

        category = self.category if self.category in _CATEGORY_KEYWORDS else "events"

        text = self._fetch_text(self.url)
        score, matches = self._keyword_score(text, category)
        verdict = self._verdict_from_score(score)

        return {
            "url": self.url,
            "category": category,
            "verdict": verdict,
            "keyword_score": score,
            "matched_keywords": sorted(matches),
            "content_length": len(text),
            "reason": self._reason(verdict, matches),
        }

    def _fetch_text(self, target_url: str) -> str:
        parsed = urlparse(target_url)
        if not parsed.scheme:
            target_url = f"https://{target_url}"

        req = Request(
            target_url,
            method="GET",
            headers={"User-Agent": "ScrapingContentValidator/2.0"},
        )

        try:
            with urlopen(req, timeout=10) as resp:
                body = resp.read(self.MAX_BYTES)
                encoding = resp.headers.get_content_charset() or "utf-8"
                html = body.decode(encoding, errors="replace")
        except HTTPError as exc:
            logger.debug("content_validator_http_error url=%s err=%s", target_url, exc)
            html = ""
        except URLError as exc:
            logger.debug("content_validator_url_error url=%s err=%s", target_url, exc)
            html = ""
        except Exception as exc:
            logger.debug("content_validator_fetch_error url=%s err=%s", target_url, exc)
            html = ""

        extractor = _HTMLTextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            logger.debug("content_validator_html_parse_error", exc_info=True)

        parsed_text = extractor.text()
        if parsed_text:
            return parsed_text.lower()

        # Fall back to URL-only signal when the page is unavailable.
        return (target_url or "").lower()

    def _keyword_score(self, text: str, category: str) -> tuple[int, set[str]]:
        keywords = _CATEGORY_KEYWORDS.get(category, _CATEGORY_KEYWORDS["events"])
        lowered = (text or "").lower()

        matches = {keyword for keyword in keywords if keyword in lowered}
        if not matches:
            return 0, set()

        coverage = len(matches) / max(len(keywords), 1)
        density = min(sum(lowered.count(m) for m in matches), 20) / 20.0
        score = int(round((coverage * 70) + (density * 30)))
        return max(0, min(score, 100)), matches

    @staticmethod
    def _verdict_from_score(score: int) -> str:
        if score >= 60:
            return "RELEVANT"
        if score >= 30:
            return "UNCERTAIN"
        return "IRRELEVANT"

    @staticmethod
    def _reason(verdict: str, matches: set[str]) -> str:
        if verdict == "RELEVANT":
            return "Keyword coverage is strong for this category"
        if verdict == "UNCERTAIN":
            return "Some category signals found but confidence is moderate"
        if matches:
            return "Category signals are weak"
        return "No category-specific content signals detected"
