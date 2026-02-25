"""
Multilingual language detection service.

Combines langdetect with script-based heuristics for reliable
Arabic / French / English classification.
"""
import logging
import re
from typing import Optional

from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

# Arabic Unicode block range
_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

SUPPORTED_LANGUAGES = {"ar", "en", "fr"}

_LANG_NAMES = {
    "ar": "Arabic",
    "en": "English",
    "fr": "French",
}


class LanguageService:
    """Detect and normalise language codes for the supported set."""

    def detect(self, text: str) -> str:
        """Return 'ar', 'en', or 'fr'."""
        if not text or len(text.strip()) < 3:
            return "en"

        # Heuristic: if >= 30 % of characters are Arabic script, it's Arabic
        arabic_chars = len(_ARABIC_RE.findall(text))
        total_alpha = sum(1 for c in text if c.isalpha())
        if total_alpha > 0 and arabic_chars / total_alpha >= 0.3:
            return "ar"

        try:
            lang = detect(text)
            if lang == "ar":
                return "ar"
            if lang == "fr":
                return "fr"
            # Everything else (including Romance languages that langdetect
            # may confuse with French) defaults to English.  The platform
            # only supports ar/fr/en — guessing "fr" for Spanish/Italian
            # caused random French responses.
            return "en"
        except LangDetectException:
            return "en"

    def language_name(self, code: str) -> str:
        return _LANG_NAMES.get(code, "English")

    def is_supported(self, code: str) -> bool:
        return code in SUPPORTED_LANGUAGES


# Singleton
_service: Optional[LanguageService] = None


def get_language_service() -> LanguageService:
    global _service
    if _service is None:
        _service = LanguageService()
    return _service
