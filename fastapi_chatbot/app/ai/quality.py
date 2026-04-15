from __future__ import annotations

import re


class QualityService:
    @staticmethod
    def translation_quality(
        source_text: str,
        translated_text: str,
        glossary: dict[str, str] | None = None,
    ) -> dict[str, float]:
        source_len = max(1, len(source_text.split()))
        target_len = max(1, len(translated_text.split()))
        length_ratio = min(target_len / source_len, source_len / target_len)

        glossary_terms = glossary or {}
        consistent_terms = 0
        for src_term, tgt_term in glossary_terms.items():
            if src_term.lower() in source_text.lower() and tgt_term.lower() in translated_text.lower():
                consistent_terms += 1
        consistency = 1.0 if not glossary_terms else consistent_terms / max(1, len(glossary_terms))

        confidence = max(0.0, min(1.0, 0.4 * length_ratio + 0.6 * consistency))
        return {
            "confidence": round(confidence, 4),
            "terminology_consistency": round(consistency, 4),
            "length_ratio": round(length_ratio, 4),
        }

    @staticmethod
    def summarization_quality(source_text: str, summary: str) -> dict[str, float]:
        src_sentences = [s.strip() for s in re.split(r"[.!?]\s+", source_text) if s.strip()]
        sum_sentences = [s.strip() for s in re.split(r"[.!?]\s+", summary) if s.strip()]

        source_tokens = set(source_text.lower().split())
        summary_tokens = set(summary.lower().split())
        coverage = len(summary_tokens & source_tokens) / max(1, len(summary_tokens))

        readability = min(1.0, max(0.0, 1.2 - (len(summary.split()) / max(1, len(sum_sentences)) / 28)))
        faithfulness = coverage

        return {
            "faithfulness": round(faithfulness, 4),
            "coverage": round(coverage, 4),
            "readability": round(readability, 4),
        }

    @staticmethod
    def hallucination_risk(source_text: str, summary: str) -> float:
        src = set(source_text.lower().split())
        sum_tokens = summary.lower().split()
        unsupported = [t for t in sum_tokens if t not in src]
        return round(min(1.0, len(unsupported) / max(1, len(sum_tokens))), 4)


_quality: QualityService | None = None


def get_quality_service() -> QualityService:
    global _quality
    if _quality is None:
        _quality = QualityService()
    return _quality
