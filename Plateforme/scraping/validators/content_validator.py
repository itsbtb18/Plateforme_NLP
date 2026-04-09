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
