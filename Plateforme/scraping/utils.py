from __future__ import annotations

from collections.abc import Iterable
from itertools import zip_longest

_TRANSLATION_STATUS_VALUES = {
    "pending",
    "translated",
    "failed",
    "partial",
    "copied",
    "missing",
}


def safe_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "null":
        return ""
    return text


def contains_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))


def normalize_translation_status(status: str | None, default: str = "pending") -> str:
    normalized = safe_text(status).lower()
    if normalized in _TRANSLATION_STATUS_VALUES:
        return normalized
    return default


def _normalize_compare_text(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _is_copied_translation(english_text: str, arabic_text: str) -> bool:
    en_norm = _normalize_compare_text(english_text)
    ar_norm = _normalize_compare_text(arabic_text)
    if not en_norm or not ar_norm:
        return False

    if en_norm == ar_norm:
        return True

    # Copied snippets often keep the English text with minor punctuation deltas.
    return en_norm in ar_norm or ar_norm in en_norm


def _arabic_char_ratio(text: str) -> float:
    value = str(text or "")
    if not value:
        return 0.0
    arabic_chars = sum(1 for ch in value if "\u0600" <= ch <= "\u06ff")
    return arabic_chars / max(len(value), 1)


def _status_for_field_pair(english_text: str, arabic_text: str) -> str:
    if not arabic_text:
        return "missing"
    if _is_copied_translation(english_text, arabic_text):
        return "copied"
    if _arabic_char_ratio(arabic_text) > 0.3:
        return "translated"
    return "copied"


def _collapse_translation_statuses(statuses: list[str]) -> str:
    if statuses and all(state == "translated" for state in statuses):
        return "translated"
    if statuses and all(state == "missing" for state in statuses):
        return "missing"
    if "translated" in statuses:
        return "partial"
    return "copied"


def get_translation_status(item_data: dict) -> str:
    ar_fields = ["title_ar", "description_ar", "short_description_ar"]
    en_fields = ["title_en", "description_en", "short_description_en"]

    statuses: list[str] = []
    for ar_field, en_field in zip(ar_fields, en_fields, strict=False):
        ar_val = safe_text(item_data.get(ar_field, ""))
        en_val = safe_text(item_data.get(en_field, ""))
        statuses.append(_status_for_field_pair(en_val, ar_val))

    return _collapse_translation_statuses(statuses)


def _infer_translation_status_from_values(
    english_values: Iterable[str | None],
    arabic_values: Iterable[str | None],
) -> str:
    statuses: list[str] = []
    for english_text, arabic_text in zip_longest(
        english_values,
        arabic_values,
        fillvalue="",
    ):
        statuses.append(
            _status_for_field_pair(safe_text(english_text), safe_text(arabic_text))
        )

    return _collapse_translation_statuses(statuses)


def infer_translation_status(
    *,
    raw_status: str | None = None,
    english_values: Iterable[str | None] = (),
    arabic_values: Iterable[str | None] = (),
) -> str:
    normalized_raw = normalize_translation_status(raw_status)
    inferred = _infer_translation_status_from_values(english_values, arabic_values)

    if normalized_raw == "failed":
        return "failed"
    if normalized_raw == "translated":
        return "translated" if inferred == "translated" else inferred
    if normalized_raw in {"partial", "copied", "missing"}:
        return inferred
    return inferred


def translation_field_credit(item: dict, field_key: str) -> float:
    if not str(field_key).endswith("_ar"):
        return 1.0

    arabic_text = safe_text(item.get(field_key))
    if not arabic_text:
        return 0.0

    english_key = f"{field_key[:-3]}_en"
    fallback_key = field_key[:-3]
    status = infer_translation_status(
        raw_status=item.get("translation_status"),
        english_values=[item.get(english_key), item.get(fallback_key)],
        arabic_values=[arabic_text],
    )

    if status == "translated":
        return 1.0
    if status == "partial":
        return 0.6
    if status == "copied":
        return 0.3
    if status == "missing":
        return 0.0
    if status == "failed":
        return 0.2
    return 0.4


def apply_translation_confidence_cap(
    score: float | int | None,
    translation_status: str | None,
) -> float | None:
    if score is None:
        return None

    normalized_status = normalize_translation_status(translation_status)
    cap = 100.0 if normalized_status == "translated" else 85.0
    bounded = max(0.0, float(score))
    return round(min(bounded, cap), 1)
