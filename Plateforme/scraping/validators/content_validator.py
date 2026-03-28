import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from scraping.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)

CATEGORY_PROFILES: dict[str, dict[str, list[str]]] = {
    "events": {
        "keywords": [
            "conference",
            "workshop",
            "call for papers",
            "deadline",
            "submit",
            "event",
            "registration",
            "conférence",
            "colloque",
            "séminaire",
            "atelier",
            "appel à communication",
            "date limite",
            "inscription",
            "مؤتمر",
            "ورشة",
            "ندوة",
            "موعد",
            "تسجيل",
        ],
        "structured_signals": [
            "datetime",
            "event",
            "schema.org/event",
            "class:event",
            "cfp",
            "deadline",
        ],
    },
    "news": {
        "keywords": [
            "article",
            "publication",
            "research",
            "paper",
            "actualité",
            "خبر",
            "بحث",
        ],
        "structured_signals": ["article tag", "<time>", "pubdate", "og:article"],
    },
    "courses": {
        "keywords": [
            "course",
            "cours",
            "lecture",
            "syllabus",
            "enroll",
            "duration",
            "level",
            "دورة",
        ],
        "structured_signals": ["schema.org/course", "duration", "instructor"],
    },
    "tools": {
        "keywords": [
            "model",
            "dataset",
            "github",
            "license",
            "download",
            "huggingface",
            "نموذج",
            "بيانات",
        ],
        "structured_signals": ["repo", "release", "version", "api"],
    },
    "institutions": {
        "keywords": [
            "university",
            "université",
            "laboratory",
            "lab",
            "research",
            "جامعة",
            "مختبر",
        ],
        "structured_signals": ["about", "contact", "department", "faculty"],
    },
}


@dataclass
class ContentSnapshot:
    title: str
    meta_description: str
    headings: list[str]
    visible_text: str
    html: str


class ContentValidator:
    """Validate whether a webpage contains content relevant to a given category."""

    CONNECT_TIMEOUT = 3.0
    READ_TIMEOUT = 7.0

    def __init__(self, url: str | None = None, category: str | None = None):
        self.url = url
        self.category = category
        self.session = requests.Session()
        self.llm = GroqLLMClient(
            timeout=getattr(settings, "GROQ_SCRAPING_TIMEOUT", 30),
            max_retries=getattr(settings, "GROQ_SCRAPING_MAX_RETRIES", 2),
        )

    def run(self) -> dict[str, Any]:
        if not self.url:
            raise ValueError("URL is required")
        if not self.category:
            raise ValueError("Category is required")
        return self.validate(self.url, self.category)

    def validate(self, url: str, category: str) -> dict[str, Any]:
        normalized_category = (category or "").strip().lower()
        if normalized_category not in CATEGORY_PROFILES:
            raise ValueError(f"Unsupported category: {category}")

        snapshot = self._fetch_page_content(url)

        keyword_score, signals_found = self._compute_keyword_match(
            snapshot=snapshot,
            category=normalized_category,
        )
        sample_items_found = self._estimate_sample_items(
            snapshot=snapshot,
            category=normalized_category,
        )

        llm_contains = None
        llm_confidence = None
        llm_reason = None
        if keyword_score < 30:
            llm_contains, llm_confidence, llm_reason = self._verify_with_llm(
                category=normalized_category,
                page_text=snapshot.visible_text[:500],
            )

        verdict = self._compute_verdict(
            keyword_score=keyword_score,
            llm_contains=llm_contains,
            llm_confidence=llm_confidence,
        )

        warning = None
        if len(snapshot.visible_text.strip()) < 250:
            warning = "Peu de contenu détecté, vérifier le sélecteur CSS"

        confidence = self._compute_confidence(
            keyword_score=keyword_score,
            llm_confidence=llm_confidence,
        )

        result = {
            "keyword_score": int(round(keyword_score)),
            "signals_found": signals_found,
            "llm_verified": bool(llm_contains) if llm_contains is not None else False,
            "confidence": round(confidence, 2),
            "verdict": verdict,
            "sample_items_found": int(sample_items_found),
            "warning": warning,
            "page_summary": {
                "title": snapshot.title,
                "meta_description": snapshot.meta_description,
                "headings": snapshot.headings,
                "visible_text_sample": snapshot.visible_text[:2000],
            },
        }

        if llm_reason:
            result["llm_reason"] = llm_reason

        return result

    def _fetch_page_content(self, url: str) -> ContentSnapshot:
        normalized = self._normalize_url(url)
        response = self.session.get(
            normalized,
            timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()

        html = response.text or ""
        soup = BeautifulSoup(html, "html.parser")

        for element in soup(["script", "style", "noscript", "svg", "canvas"]):
            element.decompose()

        title = (soup.title.string or "").strip() if soup.title else ""

        meta_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        if not meta_tag:
            meta_tag = soup.find("meta", attrs={"property": "og:description"})
        meta_description = ""
        if meta_tag and meta_tag.get("content"):
            meta_description = str(meta_tag.get("content")).strip()

        headings = []
        for heading_tag in soup.find_all(["h1", "h2", "h3"]):
            text = heading_tag.get_text(" ", strip=True)
            if text:
                headings.append(text)

        visible_text = soup.get_text(" ", strip=True)
        visible_text = re.sub(r"\s+", " ", visible_text).strip()

        return ContentSnapshot(
            title=title,
            meta_description=meta_description,
            headings=headings,
            visible_text=visible_text,
            html=html,
        )

    def _compute_keyword_match(
        self,
        *,
        snapshot: ContentSnapshot,
        category: str,
    ) -> tuple[float, list[str]]:
        profile = CATEGORY_PROFILES[category]
        keywords = profile["keywords"]

        search_blob = " ".join(
            [
                snapshot.title,
                snapshot.meta_description,
                " ".join(snapshot.headings),
                snapshot.visible_text[:2000],
            ]
        ).lower()

        found_keywords = [kw for kw in keywords if kw.lower() in search_blob]
        keyword_ratio = (len(found_keywords) / max(len(keywords), 1)) * 100.0

        signals_found = self._detect_structured_signals(
            category=category,
            snapshot=snapshot,
            search_blob=search_blob,
        )
        bonus = min(20.0, len(signals_found) * 5.0)

        score = min(100.0, keyword_ratio + bonus)
        return score, signals_found

    def _detect_structured_signals(
        self,
        *,
        category: str,
        snapshot: ContentSnapshot,
        search_blob: str,
    ) -> list[str]:
        soup = BeautifulSoup(snapshot.html or "", "html.parser")
        signals: list[str] = []

        def add(signal: str):
            if signal not in signals:
                signals.append(signal)

        profile_signals = [
            sig.lower() for sig in CATEGORY_PROFILES[category]["structured_signals"]
        ]

        if category == "events":
            if soup.find("time") or "datetime" in search_blob:
                add("datetime")
            if "schema.org/event" in snapshot.html.lower() or (
                soup.find(attrs={"itemtype": re.compile(r"event", re.I)})
            ):
                add("schema.org/Event")
            for tag in soup.find_all(True, class_=True):
                classes = [str(c) for c in (tag.get("class") or [])]
                event_class = next((c for c in classes if "event" in c.lower()), None)
                if event_class:
                    add(f"class={event_class}")
                    break
            if "cfp" in search_blob:
                add("cfp")
            if "deadline" in search_blob or "date limite" in search_blob:
                add("deadline")

        if category == "news":
            if soup.find("article"):
                add("article tag")
            if soup.find("time"):
                add("<time>")
            if "pubdate" in search_blob:
                add("pubDate")
            if soup.find("meta", attrs={"property": "og:type", "content": "article"}):
                add("og:article")

        if category == "courses":
            if "schema.org/course" in snapshot.html.lower() or soup.find(
                attrs={"itemtype": re.compile(r"course", re.I)}
            ):
                add("schema.org/Course")
            if "duration" in search_blob:
                add("duration")
            if "instructor" in search_blob or "enseignant" in search_blob:
                add("instructor")

        if category == "tools":
            for sig in ["repo", "release", "version", "api"]:
                if sig in search_blob:
                    add(sig)

        if category == "institutions":
            for sig in ["about", "contact", "department", "faculty"]:
                if sig in search_blob:
                    add(sig)

        for sig in profile_signals:
            if sig in search_blob and sig not in [s.lower() for s in signals]:
                add(sig)

        return signals

    def _verify_with_llm(
        self,
        *,
        category: str,
        page_text: str,
    ) -> tuple[bool | None, float | None, str | None]:
        if not self.llm.is_configured:
            logger.info("groq_not_configured_for_content_validator")
            return None, None, None

        prompt = (
            f"Does this webpage contain {category.upper()} content relevant to "
            "Arabic NLP research? Answer JSON: "
            "{contains: bool, confidence: float, reason: str}\n\n"
            f"Page text sample:\n{page_text}"
        )

        raw = self.llm._chat(
            system="You are a strict classifier. Return only JSON.",
            user=prompt,
        )
        if not raw:
            return None, None, None

        parsed = self._safe_parse_json(raw)
        if not isinstance(parsed, dict):
            return None, None, None

        contains = parsed.get("contains")
        confidence = parsed.get("confidence")
        reason = parsed.get("reason")

        contains_value = bool(contains) if isinstance(contains, bool) else None
        confidence_value = None
        if isinstance(confidence, (int, float)):
            confidence_value = max(0.0, min(1.0, float(confidence)))

        reason_value = str(reason).strip() if reason is not None else None
        return contains_value, confidence_value, reason_value

    @staticmethod
    def _safe_parse_json(raw: str) -> dict[str, Any] | None:
        cleaned = raw.strip()
        cleaned = re.sub(r"```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip().rstrip("`")

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]+\}", cleaned)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    return None
        return None

    @staticmethod
    def _compute_verdict(
        *,
        keyword_score: float,
        llm_contains: bool | None,
        llm_confidence: float | None,
    ) -> str:
        if keyword_score >= 60:
            return "RELEVANT"

        if llm_contains is True and (llm_confidence or 0.0) >= 0.6:
            return "RELEVANT"

        if keyword_score < 30:
            if llm_contains is False and (llm_confidence or 0.0) >= 0.6:
                return "IRRELEVANT"
            return "UNCERTAIN"

        if keyword_score < 45:
            return "UNCERTAIN"

        return "RELEVANT"

    @staticmethod
    def _compute_confidence(
        *,
        keyword_score: float,
        llm_confidence: float | None,
    ) -> float:
        score_confidence = max(0.0, min(1.0, keyword_score / 100.0))
        if llm_confidence is None:
            return score_confidence
        return (score_confidence * 0.6) + (llm_confidence * 0.4)

    @staticmethod
    def _normalize_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raise ValueError("URL is required")
        parsed = urlparse(raw)
        if not parsed.scheme:
            return f"https://{raw}"
        return raw

    def _estimate_sample_items(
        self, *, snapshot: ContentSnapshot, category: str
    ) -> int:
        soup = BeautifulSoup(snapshot.html or "", "html.parser")

        if category == "events":
            selectors = ["article", "[class*='event']", "[id*='event']"]
        elif category == "news":
            selectors = ["article", "[class*='news']", "[class*='post']"]
        elif category == "courses":
            selectors = ["[class*='course']", "[class*='lesson']", "article"]
        elif category == "tools":
            selectors = ["[class*='tool']", "[class*='repo']", "article"]
        else:
            selectors = [
                "[class*='institution']",
                "[class*='faculty']",
                "[class*='department']",
                "article",
            ]

        count = 0
        for selector in selectors:
            try:
                count = max(count, len(soup.select(selector)))
            except Exception:
                continue

        if count == 0 and snapshot.visible_text:
            fallback_tokens = {
                "events": ["event", "conference", "atelier", "مؤتمر"],
                "news": ["article", "publication", "actualité", "خبر"],
                "courses": ["course", "lecture", "cours", "دورة"],
                "tools": ["tool", "model", "dataset", "نموذج"],
                "institutions": ["university", "laboratory", "université", "جامعة"],
            }
            lowered = snapshot.visible_text.lower()
            count = sum(
                lowered.count(token.lower()) for token in fallback_tokens[category]
            )

        return count
