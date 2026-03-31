import json
import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup
from django.utils import timezone

from scraping.constants import (
    CUSTOM_SCRAPER_CLEANUP_SELECTORS,
    CUSTOM_SCRAPER_CLEANUP_TAGS,
    CUSTOM_SELECTOR_DESC_FALLBACK,
    CUSTOM_SELECTOR_LINK_FALLBACK,
    CUSTOM_SELECTOR_TITLE_FALLBACK,
)
from scraping.file_downloader import attach_file_to_model, try_download_image
from scraping.fixture_loader import load_custom_scraper_taxonomy
from scraping.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


_DEFAULT_CATEGORY_KEYWORDS = {
    "events": ["conference", "workshop", "seminar", "cfp"],
    "tools": ["model", "dataset", "huggingface", "github", "tool", "library"],
    "news": ["arxiv", "paper", "publication", "research", "news"],
    "courses": [
        "course",
        "mooc",
        "coursera",
        "udemy",
        "youtube",
        "lecture",
        "syllabus",
    ],
    "institutions": [
        "university",
        "lab",
        "centre",
        "research group",
        "institute",
    ],
}

_DEFAULT_TOOL_TYPE_KEYWORDS = {
    "machine_translation": ["translation", "translate"],
    "sentiment_analysis": ["sentiment", "opinion mining"],
    "ner": ["named entity", "ner"],
    "pos_tagging": ["part-of-speech", "pos tagging", "pos"],
    "stemming": ["stem", "stemming", "lemmat"],
    "tokenization": ["token", "tokenization", "segment"],
}

_DEFAULT_COURSE_LEVEL_MAP = {
    "beginner": "bachelor",
    "introductory": "bachelor",
    "intermediate": "master",
    "advanced": "doctorate",
}

_DEFAULT_COURSE_PLATFORM_MAP = {
    "coursera": "coursera",
    "youtube": "youtube",
    "mit": "mit",
    "edx": "edx",
    "university": "university",
}

_DEFAULT_INSTITUTION_TYPE_MAP = {
    "university": "University",
    "research lab": "Research Center",
    "lab": "Research Center",
    "center": "Research Center",
    "centre": "Research Center",
    "school": "School",
    "other": "Other",
}

_CUSTOM_TAXONOMY = load_custom_scraper_taxonomy()


def _taxonomy_map(key: str, fallback: dict):
    candidate = _CUSTOM_TAXONOMY.get(key)
    if isinstance(candidate, dict) and candidate:
        return candidate
    return fallback


class CustomDomainScraper(BaseScraper):
    """
    Scrapes any custom domain added by admin.
    Uses LLM to extract structured data from unknown layouts.
    Falls back to RSS if available.
    """

    CATEGORY_KEYWORDS = _taxonomy_map("category_keywords", _DEFAULT_CATEGORY_KEYWORDS)

    TOOL_TYPE_KEYWORDS = _taxonomy_map(
        "tool_type_keywords", _DEFAULT_TOOL_TYPE_KEYWORDS
    )

    COURSE_LEVEL_MAP = _taxonomy_map("course_level_map", _DEFAULT_COURSE_LEVEL_MAP)

    COURSE_PLATFORM_MAP = _taxonomy_map(
        "course_platform_map", _DEFAULT_COURSE_PLATFORM_MAP
    )

    INSTITUTION_TYPE_MAP = _taxonomy_map(
        "institution_type_map", _DEFAULT_INSTITUTION_TYPE_MAP
    )

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.category = self._normalize_category(getattr(source, "category", ""))
        self.detected_category = None
        self.items_failed = 0

    def scrape(self):
        results = []
        resolved_category = self._resolve_effective_category(
            self.source.base_url,
            page_text="",
        )
        self.category = resolved_category

        # Step 1: try RSS first if enabled
        if self.source.use_rss:
            rss_scraper = self.get_rss_scraper()
            feed_url = rss_scraper.detect_feed_url(self.source.base_url)
            if feed_url:
                rss_items = rss_scraper.scrape_feed(feed_url, resolved_category)
                if rss_items:
                    results.extend(self._save_rss_items(rss_items, resolved_category))
                    return results

        # Step 2: HTML scraping with LLM extraction
        response = self.safe_request(self.source.base_url)
        if not response:
            return results

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove nav, footer, scripts
        for tag in soup(CUSTOM_SCRAPER_CLEANUP_TAGS):
            tag.decompose()
        for selector in CUSTOM_SCRAPER_CLEANUP_SELECTORS:
            for node in soup.select(selector):
                node.decompose()

        # Try to find main content container
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(id="main")
            or soup.find(class_="content")
            or soup.find(class_="main")
            or soup  # fallback to full page
        )

        # Extract clean text for LLM
        page_text = main_content.get_text(separator="\n", strip=True)[:12000]

        resolved_category = self._resolve_effective_category(
            self.source.base_url,
            page_text=page_text,
        )
        self.category = resolved_category

        if self.source.use_llm_extraction:
            items = self._extract_with_llm(page_text, resolved_category)
        else:
            items = self._extract_with_selectors(
                soup,
                self.source.scrape_config,
                resolved_category,
            )

        for item in items:
            try:
                result = self._save_item(item, resolved_category)
                if result:
                    results.append(result)
                else:
                    self.items_skipped += 1
            except Exception as e:
                self.items_failed = getattr(self, "items_failed", 0) + 1
                self._log_error(
                    "custom_scraper_save", str(e), source=item.get("title", "unknown")
                )

        return results

    def _normalize_category(self, category):
        value = (category or "").strip().lower()
        return value if value in self.CATEGORY_KEYWORDS else ""

    def _resolve_effective_category(self, source_url, page_text=""):
        config = self.source.scrape_config or {}
        explicit_category = self._normalize_category(
            getattr(self.source, "category", "")
        )
        override_category = self._normalize_category(
            config.get("category_override", "")
        )
        auto_detect = bool(config.get("auto_detect_category", False))

        if override_category:
            return override_category

        if explicit_category and not auto_detect:
            return explicit_category

        detected = self._detect_category(source_url, page_text)
        if detected:
            self.detected_category = detected
            return detected

        return explicit_category or "events"

    def _detect_category(self, source_url, page_text):
        return self.detect_category_from_signals(source_url, page_text)

    @classmethod
    def detect_category_from_signals(cls, source_url, page_text):
        url_text = (source_url or "").lower()
        body_text = (page_text or "").lower()
        combined = f"{url_text}\n{body_text}"
        scores = {category: 0 for category in cls.CATEGORY_KEYWORDS}

        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                escaped = re.escape(keyword)
                if re.search(rf"\b{escaped}\b", combined):
                    scores[category] += 1
                if keyword in url_text:
                    scores[category] += 2

        best_category = max(scores, key=scores.get)
        if scores[best_category] <= 0:
            return "events"
        return best_category

    def _extract_with_llm(self, page_text, category):
        from scraping.llm_validation import (
            GroqLLMClient,
            build_custom_extraction_prompt,
        )

        client = GroqLLMClient()
        system_prompt, user_prompt = build_custom_extraction_prompt(category, page_text)
        try:
            response_text = client._chat(system_prompt, user_prompt)
            if not response_text:
                raise RuntimeError("Empty response from LLM")

            data = self._parse_llm_array(response_text)
            return [self._normalize_extracted_item(category, item) for item in data]
        except Exception as exc:
            self._log_error(
                "llm_extraction_failed",
                f"{type(exc).__name__}: {exc}",
                source=self.source.base_url or self.source.name,
                url=self.source.base_url or "",
            )
            logger.warning(
                "LLM call failed source=%s category=%s exc_type=%s message=%s",
                self.source.base_url or self.source.name,
                category,
                type(exc).__name__,
                str(exc),
            )
        return []

    def _parse_llm_array(self, raw_text):
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                return parsed["items"]
        except json.JSONDecodeError as exc:
            logger.debug(
                "custom_scraper_llm_json_parse_fallback",
                extra={"error": str(exc), "context": raw_text[:120]},
            )

        json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            if isinstance(parsed, list):
                return parsed
        raise ValueError("LLM response did not contain a valid JSON array")

    def _normalize_extracted_item(self, category, item):
        if not isinstance(item, dict):
            return {}

        base = {
            "title": (item.get("title") or item.get("name") or "").strip(),
            "name": (item.get("name") or item.get("title") or "").strip(),
            "description": (
                item.get("description")
                or item.get("summary")
                or item.get("what_it_does")
                or ""
            ).strip(),
            "url": (
                item.get("url")
                or item.get("website")
                or item.get("github_link")
                or item.get("github_url")
                or ""
            ).strip(),
            "date": item.get("date"),
        }

        if category == "tools":
            base["tool_type"] = self._infer_tool_type(item)
            base["github_url"] = (
                item.get("github_link") or item.get("github_url") or ""
            ).strip()
            base["documentation_link"] = (
                item.get("documentation_link")
                or item.get("docs")
                or item.get("documentation")
                or ""
            ).strip()
            base["language_support"] = self._to_list(
                item.get("language_support")
                or item.get("supported_languages")
                or item.get("languages")
            )
            base["license"] = (item.get("license") or "").strip()
            base["installation_instructions"] = (
                item.get("installation_command") or item.get("installation") or ""
            ).strip()
        elif category == "courses":
            base["institution"] = (
                item.get("institution") or item.get("provider") or ""
            ).strip()
            base["level"] = (
                item.get("level") or item.get("course_level") or ""
            ).strip()
            base["instructor"] = (
                item.get("instructor") or item.get("instructor_name") or ""
            ).strip()
            base["platform"] = (
                item.get("platform") or item.get("platform_name") or ""
            ).strip()
            base["language"] = (
                item.get("language") or item.get("language_of_instruction") or ""
            ).strip()
            base["duration"] = (item.get("duration") or "").strip()
            base["is_free"] = item.get("is_free")
            base["access_link"] = (item.get("access_link") or base["url"]).strip()
        elif category == "institutions":
            base["acronym"] = (item.get("acronym") or "").strip()
            base["institution_type"] = (
                item.get("type") or item.get("institution_type") or ""
            ).strip()
            base["country"] = (item.get("country") or "").strip()
            base["city"] = (item.get("city") or "").strip()
            base["website"] = (item.get("website") or base["url"]).strip()
            base["research_specialties"] = self._to_list(
                item.get("research_specialties") or item.get("main_research_areas")
            )
            base["director"] = (
                item.get("director") or item.get("director_name") or ""
            ).strip()
            base["logo_url"] = (item.get("logo_url") or "").strip()
        elif category == "events":
            base["location"] = (item.get("location") or "").strip()
            base["event_type"] = (item.get("event_type") or "").strip()
            base["registration_link"] = (item.get("registration_link") or "").strip()
        elif category == "news":
            base["source_name"] = (item.get("source_name") or "").strip()

        return base

    def _extract_with_selectors(self, soup, config, category):
        items = []
        config = config or {}
        configured_title = (config.get("title_selector") or "").strip()
        configured_desc = (config.get("desc_selector") or "").strip()
        configured_link = (config.get("link_selector") or "").strip()

        title_sel = configured_title or CUSTOM_SELECTOR_TITLE_FALLBACK
        desc_sel = configured_desc or CUSTOM_SELECTOR_DESC_FALLBACK
        link_sel = configured_link or CUSTOM_SELECTOR_LINK_FALLBACK

        if not (configured_title and configured_desc and configured_link):
            missing = [
                key
                for key, value in (
                    ("title_selector", configured_title),
                    ("desc_selector", configured_desc),
                    ("link_selector", configured_link),
                )
                if not value
            ]
            logger.warning(
                "custom_selector_fallback_used source=%s category=%s missing=%s",
                self.source.base_url or self.source.name,
                category,
                ",".join(missing),
            )

        titles = soup.select(title_sel)
        for t in titles[:20]:
            item = {
                "title": t.get_text(strip=True),
                "description": "",
                "url": "",
                "date": None,
            }
            next_p = t.find_next(desc_sel.split(",")[0].strip())
            if next_p:
                item["description"] = next_p.get_text(strip=True)[:300]
            link = t.select_one(link_sel) or t.find_next(link_sel.split(",")[0].strip())
            if link and link.get("href"):
                item["url"] = link["href"]
            if item["title"]:
                items.append(self._normalize_extracted_item(category, item))
        return items

    def _save_rss_items(self, rss_items, category):
        saved = []
        for item in rss_items:
            normalized = self._normalize_extracted_item(
                category,
                {
                    "title": item.get("title_en") or item.get("title", ""),
                    "description": item.get("description_en")
                    or item.get("description", ""),
                    "url": item.get("url", ""),
                    "date": item.get("published_date"),
                    "source_name": item.get("source_name", ""),
                },
            )
            result = self._save_item(normalized, category)
            if result:
                saved.append(result)
        return saved

    def _save_item(self, item, category):
        """
        Save item to the appropriate model based on category.
        Returns item dict if created, None if skipped.
        """
        title = (item.get("title") or item.get("name") or "").strip()
        if not title or len(title) < 3:
            return None

        try:
            if category == "events":
                return self._save_as_event(item)
            if category == "tools":
                return self._save_as_tool(item)
            if category == "news":
                return self._save_as_news(item)
            if category == "courses":
                return self._save_as_course(item)
            if category == "institutions":
                return self._save_as_institution(item)
            return None
        except Exception as e:
            self._log_error("custom_save", str(e), source=title)
            return None

    def _save_as_event(self, item):
        from events.models import Event

        title = item.get("title", "").strip()
        if not title:
            return None
        item_url = (item.get("url") or "").strip()
        if Event.objects.filter(title_en__iexact=title).exists():
            return None
        if item_url and Event.objects.filter(website=item_url).exists():
            return None

        start_date = self._parse_date(item.get("date")) or timezone.now().date()
        end_date = self._parse_date(item.get("end_date")) or start_date
        if end_date < start_date:
            end_date = start_date

        organizer = self._get_default_institution(
            item.get("organizer") or self.source.name or "Custom Source"
        )
        if organizer is None:
            return None

        description = item.get("description", "")[:1000]
        if not description:
            description = title

        event = Event.objects.create(
            title_en=title[:200],
            title_ar=title[:200],
            title=title[:200],
            description=description,
            description_en=description,
            description_ar=description,
            website=item_url,
            source_url=item_url,
            source_name=self.source.name,
            event_type=self._normalize_event_type(item.get("event_type")),
            domains="nlp",
            start_date=start_date,
            end_date=end_date,
            registration_link=item.get("registration_link") or None,
            location=item.get("location", "")[:255],
            location_en=item.get("location", "")[:255],
            location_ar=item.get("location", "")[:255],
            language=self._normalize_language(item.get("language")),
            organizer=organizer,
            contact_email="scraper-bot@nlp-platform.local",
            approval_status="pending",
            created_by=self.get_system_user(),
            source="custom_scrape",
        )
        return {"title_en": title, "id": str(event.id)}

    def _save_as_news(self, item):
        from feed.models import Post

        title = item.get("title", "").strip()
        if not title:
            return None
        source_url = (item.get("url") or "").strip()
        if Post.objects.filter(title_en__iexact=title).exists():
            return None
        if source_url and Post.objects.filter(source_url=source_url).exists():
            return None

        content = item.get("description", "") or title

        post = Post.objects.create(
            title_en=title[:200],
            title_ar=title[:200],
            title=title[:200],
            content=content,
            content_en=content,
            content_ar=content,
            source_url=source_url,
            source_name=item.get("source_name") or self.source.name,
            published_date=self._parse_date(item.get("date")),
            news_category="news",
            approval_status="pending",
            author=self.get_system_user(),
        )
        return {"title_en": title, "id": str(post.id)}

    def _save_as_tool(self, item):
        from resources.models import NLPTool

        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            return None

        description = (item.get("description") or "").strip()
        if not description:
            description = name

        github_url = (item.get("github_url") or "").strip()
        access_link = (
            item.get("url") or github_url or item.get("documentation_link") or ""
        ).strip()
        if NLPTool.objects.filter(title_en__iexact=name).exists():
            return None
        if github_url and NLPTool.objects.filter(github_url=github_url).exists():
            return None
        if access_link and NLPTool.objects.filter(access_link=access_link).exists():
            return None

        supported_languages = self._normalize_tool_supported_language(
            item.get("language_support")
        )
        primary_language = "ar" if supported_languages == "ar" else "en"

        tool = NLPTool.objects.create(
            title=name[:200],
            title_en=name[:200],
            title_ar=name[:200],
            description=description,
            description_en=description,
            description_ar=description,
            tool_type=self._normalize_tool_type(item.get("tool_type"), description),
            version=(item.get("version") or "unknown")[:20],
            access_link=access_link or None,
            documentation_link=(item.get("documentation_link") or "").strip() or None,
            github_url=github_url or None,
            license=(item.get("license") or "").strip() or None,
            installation_instructions=(
                item.get("installation_instructions") or ""
            ).strip()
            or None,
            source_url=access_link or None,
            source_name=self.source.name,
            supported_languages=supported_languages,
            language=primary_language,
            approval_status="pending",
            author=self.get_system_user(),
        )
        return {"title_en": name, "id": str(tool.id)}

    def _save_as_course(self, item):
        from resources.models import Course

        title = (item.get("title") or item.get("name") or "").strip()
        if not title:
            return None

        access_link = (item.get("access_link") or item.get("url") or "").strip()
        if Course.objects.filter(title_en__iexact=title).exists():
            return None
        if access_link and Course.objects.filter(access_link=access_link).exists():
            return None

        description = (item.get("description") or "").strip() or title
        level = self._normalize_course_level(item.get("level"))
        platform = self._normalize_course_platform(item.get("platform"), access_link)
        language = self._normalize_language(item.get("language"))
        provider = item.get("institution") or self.source.name or "Custom Provider"
        institution = self._get_default_institution(provider, website=access_link)
        if institution is None:
            return None

        now = timezone.now()
        academic_year = f"{now.year}-{now.year + 1}"
        user = self.get_system_user()

        course = Course.objects.create(
            title=title[:200],
            title_en=title[:200],
            title_ar=title[:200],
            description=description,
            description_en=description,
            description_ar=description,
            access_link=access_link or None,
            author=user,
            language=language,
            field="nlp",
            academic_level=level,
            teacher=user,
            institution=institution,
            academic_year=academic_year,
            instructor=(item.get("instructor") or "")[:255] or None,
            duration=(item.get("duration") or "")[:100] or None,
            platform=platform,
            enrollment_url=access_link or None,
            is_free=self._to_bool(item.get("is_free"), default=True),
            source_url=access_link or None,
            source_name=self.source.name,
            approval_status="pending",
        )
        return {"title_en": title, "id": str(course.id)}

    def _save_as_institution(self, item):
        from institutions.models import Institution

        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            return None

        website = (item.get("website") or item.get("url") or "").strip()
        if Institution.objects.filter(name_en__iexact=name).exists():
            return None
        if website and Institution.objects.filter(website=website).exists():
            return None

        country_name = (item.get("country") or "Unknown").strip() or "Unknown"
        country = self.get_or_create_country(
            country_name, code=self._country_code(country_name)
        )
        inst_type = self._normalize_institution_type(item.get("institution_type"))
        city = (item.get("city") or "").strip()
        description = (item.get("description") or name).strip()

        research_areas = self._to_list(item.get("research_specialties"))
        if research_areas:
            description = (
                f"{description}\n\nResearch areas: {', '.join(research_areas)}"
            )

        address = ", ".join([part for part in [city, country_name] if part])

        institution = Institution.objects.create(
            name=name[:255],
            name_en=name[:255],
            name_ar=name[:255],
            acronym=(item.get("acronym") or "")[:20],
            type=inst_type,
            country=country,
            city=city[:100],
            city_en=city[:100],
            city_ar=city[:100],
            website=website,
            address=address,
            address_en=address,
            address_ar=address,
            description=description,
            description_en=description,
            description_ar=description,
            director=(item.get("director") or "")[:255] or None,
            source_url=website or None,
            source_name=self.source.name,
            approval_status="pending",
            created_by=self.get_system_user(),
        )

        logo_url = (item.get("logo_url") or "").strip()
        if logo_url:
            image_file, filename = try_download_image(
                [logo_url],
                "institutions",
                item_name=name,
            )
            if filename:
                try:
                    attach_file_to_model(institution, "logo", image_file, filename)
                except Exception:
                    logger.debug("Failed to attach institution logo for %s", name)

        return {"name_en": name, "id": str(institution.id)}

    def _infer_tool_type(self, item):
        source = " ".join(
            [
                str(item.get("tool_type") or ""),
                str(item.get("description") or ""),
                str(item.get("what_it_does") or ""),
                str(item.get("name") or item.get("title") or ""),
            ]
        ).lower()
        for tool_type, keywords in self.TOOL_TYPE_KEYWORDS.items():
            if any(keyword in source for keyword in keywords):
                return tool_type
        return "tokenization"

    def _normalize_tool_type(self, value, description):
        raw = (value or "").strip().lower()
        if raw in self.TOOL_TYPE_KEYWORDS:
            return raw
        return self._infer_tool_type({"tool_type": raw, "description": description})

    def _normalize_tool_supported_language(self, value):
        values = self._to_list(value)
        lowered = [v.lower() for v in values]
        if any(v in {"ar", "arabic", "arab"} for v in lowered):
            return "ar"
        if any(v in {"en", "english"} for v in lowered):
            return "en"
        if any(v in {"fr", "french"} for v in lowered):
            return "fr"
        if any(v in {"es", "spanish"} for v in lowered):
            return "es"
        return "ar"

    def _normalize_course_level(self, value):
        raw = (value or "").strip().lower()
        if raw in {"bachelor", "master", "doctorate"}:
            return raw
        return self.COURSE_LEVEL_MAP.get(raw, "master")

    def _normalize_course_platform(self, value, access_link):
        raw = (value or "").strip().lower()
        if raw in self.COURSE_PLATFORM_MAP:
            return self.COURSE_PLATFORM_MAP[raw]
        link = (access_link or "").lower()
        if "coursera" in link:
            return "coursera"
        if "youtube" in link or "youtu.be" in link:
            return "youtube"
        if "mit" in link:
            return "mit"
        if "edx" in link:
            return "edx"
        if link:
            return "university"
        return "other"

    def _normalize_institution_type(self, value):
        raw = (value or "").strip().lower()
        for key, mapped in self.INSTITUTION_TYPE_MAP.items():
            if key in raw:
                return mapped
        return "University"

    def _normalize_event_type(self, value):
        raw = (value or "").strip().lower()
        if "workshop" in raw:
            return "workshop"
        if "seminar" in raw:
            return "seminar"
        if "cfp" in raw or "call" in raw:
            return "call_for_papers"
        if "hack" in raw:
            return "hackathon"
        if "conference" in raw:
            return "conference"
        return "other"

    def _normalize_language(self, value):
        raw = (value or "").strip().lower()
        if raw.startswith("ar") or "arab" in raw:
            return "ar"
        if raw.startswith("fr") or "french" in raw:
            return "fr"
        return "en"

    def _parse_date(self, value):
        if not value:
            return None
        if hasattr(value, "date"):
            try:
                return value.date()
            except Exception as exc:
                logger.debug(
                    "date_parse_fallback",
                    extra={"raw": str(value), "error": str(exc)},
                )
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            try:
                return value
            except Exception as exc:
                logger.debug(
                    "date_parse_fallback",
                    extra={"raw": str(value), "error": str(exc)},
                )
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception as exc:
                logger.debug(
                    "date_parse_fallback",
                    extra={"raw": value, "error": str(exc)},
                )
                continue
        return None

    def _country_code(self, country_name):
        base = re.sub(r"[^A-Za-z]", "", (country_name or "")).upper()
        if len(base) >= 2:
            return base[:2]
        return "XX"

    def _get_default_institution(self, name, website=""):
        country = self.get_or_create_country("International", "XX")
        return self.get_or_create_institution(
            name,
            country=country,
            city="",
            website=website,
            inst_type="University",
        )

    def _to_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = [p.strip() for p in re.split(r"[,;|]", value) if p.strip()]
            return parts
        return [str(value).strip()]

    def _to_bool(self, value, default=True):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "free"}:
            return True
        if text in {"0", "false", "no", "n", "paid"}:
            return False
        return default
