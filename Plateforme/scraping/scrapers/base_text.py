"""Text utility BaseScraper mixin."""


class TextMixin:
    def parse_date(self, date_str, default=None):
        return super().parse_date(date_str, default)

    def truncate(self, text: str, max_len: int = 200) -> str:
        return super().truncate(text, max_len)

    def clean_text(self, text: str) -> str:
        return super().clean_text(text)

    def normalize_arabic_text(self, text):
        return super().normalize_arabic_text(text)

    def detect_arabic_ratio(self, text):
        return super().detect_arabic_ratio(text)

    def detect_language(self, text):
        return super().detect_language(text)

    def is_relevant_language(self, text):
        return super().is_relevant_language(text)

    def _normalize_text(self, value: str) -> str:
        return super()._normalize_text(value)

    def _normalize_url(self, value: str, strip_www: bool = False) -> str:
        return super()._normalize_url(value, strip_www)

    def _title_similarity(self, left: str, right: str) -> float:
        return super()._title_similarity(left, right)
