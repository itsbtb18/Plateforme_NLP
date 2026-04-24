"""Dedup-related BaseScraper mixin."""


class DedupMixin:
    def _set_duplicate_match(self, existing_obj):
        return super()._set_duplicate_match(existing_obj)

    def _record_duplicate_skip(
        self, category: str, item_data: dict, reason: str, match_score: float = 0.0
    ):
        return super()._record_duplicate_skip(
            category, item_data, reason, match_score=match_score
        )

    def _normalize_skip_reason(self, reason: str) -> str:
        return super()._normalize_skip_reason(reason)

    def _dedup_event(self, item_data: dict) -> tuple[bool, str, float]:
        return super()._dedup_event(item_data)

    def _dedup_tool(self, item_data: dict) -> tuple[bool, str, float]:
        return super()._dedup_tool(item_data)

    def _dedup_news(self, item_data: dict) -> tuple[bool, str, float]:
        return super()._dedup_news(item_data)

    def _dedup_course(self, item_data: dict) -> tuple[bool, str, float]:
        return super()._dedup_course(item_data)

    def _dedup_institution(self, item_data: dict) -> tuple[bool, str, float]:
        return super()._dedup_institution(item_data)

    def _check_duplicate_policy(self, category, item_data) -> tuple[bool, str, float]:
        return super()._check_duplicate_policy(category, item_data)

    def is_duplicate(self, title, category, model_class):
        return super().is_duplicate(title, category, model_class)
