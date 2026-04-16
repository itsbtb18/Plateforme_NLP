from __future__ import annotations

import re

from app.config import get_settings
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider


class TranslationSummarizationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = {
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
        }

    def provider_order(self) -> list[str]:
        primary = self.settings.TS_PRIMARY_PROVIDER.strip().lower()
        fallback = self.settings.TS_FALLBACK_PROVIDER.strip().lower()

        valid = {"gemini", "groq"}
        if primary not in valid:
            primary = "gemini"
        if fallback not in valid or fallback == primary:
            fallback = "groq" if primary == "gemini" else "gemini"

        return [primary, fallback]

    async def translate(self, *, text: str, source_language: str, target_language: str) -> tuple[str, str, bool]:
        errors: list[str] = []
        prepared_text = self._prepare_text_for_translation(text)
        chunks = self._split_into_chunks(prepared_text)
        order = self.provider_order()
        for idx, name in enumerate(order):
            provider = self.providers[name]
            try:
                translated_chunks: list[str] = []
                for chunk in chunks:
                    translated = await provider.translate(
                        text=chunk,
                        source_language=source_language,
                        target_language=target_language,
                    )
                    translated = self._post_process_translation(translated)
                    if self._looks_like_summary(source_text=chunk, translated_text=translated):
                        raise RuntimeError("provider output looks summarized/compressed, not full translation")
                    translated_chunks.append(translated)

                output = self._merge_chunks(translated_chunks)
                if self._looks_like_summary(source_text=text, translated_text=output):
                    raise RuntimeError("provider output looks summarized/compressed, not full translation")
                return output, name, idx > 0
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
        raise RuntimeError("All providers failed: " + " | ".join(errors))

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> tuple[str, str, bool]:
        errors: list[str] = []
        prepared_text = self._prepare_text_for_summarization(text)
        sections = self._split_into_sections(prepared_text)
        order = self.provider_order()
        for idx, name in enumerate(order):
            provider = self.providers[name]
            try:
                summarized_sections: list[dict[str, str | int]] = []
                for section in sections:
                    section_title = str(section["title"])
                    section_level = int(section["level"])
                    section_body = str(section["content"]).strip() or section_title

                    section_chunks = self._split_into_chunks(section_body, max_chars=2800)
                    chunk_summaries: list[str] = []
                    for chunk in section_chunks:
                        words = len(chunk.split())
                        section_target_words = self._estimate_section_summary_words(words, max_words)
                        chunk_summary = await provider.summarize(
                            text=chunk,
                            language=language,
                            style=f"section::{style}",
                            max_words=section_target_words,
                        )
                        chunk_summaries.append(self._post_process_summary(chunk_summary))

                    if len(chunk_summaries) > 1:
                        merged_for_section = "\n\n".join(chunk_summaries)
                        final_words = self._estimate_section_summary_words(len(section_body.split()), max_words)
                        section_summary = await provider.summarize(
                            text=merged_for_section,
                            language=language,
                            style=f"section-final::{style}",
                            max_words=final_words,
                        )
                        section_summary = self._post_process_summary(section_summary)
                    else:
                        section_summary = chunk_summaries[0] if chunk_summaries else ""

                    summarized_sections.append(
                        {
                            "title": section_title,
                            "level": section_level,
                            "summary": section_summary,
                        }
                    )

                output = self._render_structured_summary(summarized_sections)
                return output, name, idx > 0
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
        raise RuntimeError("All providers failed: " + " | ".join(errors))

    @staticmethod
    def _looks_like_summary(*, source_text: str, translated_text: str) -> bool:
        source = (source_text or "").strip()
        output = (translated_text or "").strip()
        if not source or not output:
            return True

        src_words = len(source.split())
        out_words = len(output.split())
        ratio = out_words / max(src_words, 1)

        # For sufficiently long inputs, a very short output is usually a summary/compression.
        if src_words >= 120 and ratio < 0.45:
            return True

        lower_output = output.lower()
        summary_markers = [
            "executive summary",
            "section summaries",
            "key points",
            "key conclusions",
            "in summary",
            "summary:",
        ]
        if any(marker in lower_output for marker in summary_markers):
            return True

        # Too few lines compared to large multi-line source may indicate compression.
        src_non_empty_lines = len([ln for ln in re.split(r"\r?\n", source) if ln.strip()])
        out_non_empty_lines = len([ln for ln in re.split(r"\r?\n", output) if ln.strip()])
        if src_non_empty_lines >= 20 and out_non_empty_lines < max(5, src_non_empty_lines // 4):
            return True

        return False

    @staticmethod
    def _prepare_text_for_translation(text: str) -> str:
        prepared = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        # Fix soft hyphenation and noisy spacing from PDF extraction.
        prepared = re.sub(r"(?<=\w)-\n(?=\w)", "", prepared)
        prepared = re.sub(r"[ \t]+", " ", prepared)
        prepared = re.sub(r"\n{3,}", "\n\n", prepared)
        return prepared.strip()

    @staticmethod
    def _split_into_chunks(text: str, max_chars: int = 3200) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            return [text]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        def flush() -> None:
            nonlocal current, current_len
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0

        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                flush()
                chunks.extend(TranslationSummarizationService._split_large_paragraph(paragraph, max_chars))
                continue

            projected = current_len + len(paragraph) + (2 if current else 0)
            if projected > max_chars:
                flush()
            current.append(paragraph)
            current_len += len(paragraph) + (2 if len(current) > 1 else 0)

        flush()
        return chunks or [text]

    @staticmethod
    def _split_large_paragraph(paragraph: str, max_chars: int) -> list[str]:
        sentences = [s.strip() for s in re.split(r"(?<=[\.!\?؟])\s+", paragraph) if s.strip()]
        if not sentences:
            return [paragraph[:max_chars]] + ([paragraph[max_chars:]] if len(paragraph) > max_chars else [])

        parts: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    parts.append(current)
                if len(sentence) <= max_chars:
                    current = sentence
                else:
                    # Hard split for very long sentence.
                    hard_parts = [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]
                    parts.extend(hard_parts[:-1])
                    current = hard_parts[-1]
        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _post_process_translation(text: str) -> str:
        output = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        output = re.sub(r"[ \t]+", " ", output)
        output = re.sub(r"\n{3,}", "\n\n", output)
        # Light punctuation spacing cleanup.
        output = re.sub(r"\s+([,.;:!?])", r"\1", output)
        output = re.sub(r"([\(\[\{])\s+", r"\1", output)
        output = re.sub(r"\s+([\)\]\}])", r"\1", output)
        return output.strip()

    @staticmethod
    def _merge_chunks(chunks: list[str]) -> str:
        return "\n\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()

    @staticmethod
    def _prepare_text_for_summarization(text: str) -> str:
        prepared = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        prepared = re.sub(r"(?<=\w)-\n(?=\w)", "", prepared)
        prepared = re.sub(r"[ \t]+", " ", prepared)
        prepared = re.sub(r"\n{3,}", "\n\n", prepared)
        return prepared.strip()

    @staticmethod
    def _is_heading_candidate(paragraph: str, next_paragraph: str | None) -> bool:
        line = (paragraph or "").strip()
        if not line:
            return False

        words = re.findall(r"\w+", line, flags=re.UNICODE)
        word_count = len(words)
        if word_count == 0:
            return False

        if len(line) > 140 or word_count > 16:
            return False

        if re.match(r"^\s*(\d+(?:\.\d+)*|[IVXLCM]+|[A-Z]|[A-Za-z]\))\s+", line):
            return True

        letters = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ\u0600-\u06FF]", line)
        uppercase_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
        upper_ratio = (len(uppercase_letters) / len(letters)) if letters else 0.0
        if upper_ratio >= 0.65 and word_count <= 12:
            return True

        if line.endswith(":") and word_count <= 12:
            return True

        if next_paragraph and len(next_paragraph.strip()) > 80 and word_count <= 10:
            return True

        return False

    @staticmethod
    def _infer_heading_level(title: str) -> int:
        line = (title or "").strip()
        match = re.match(r"^(\d+(?:\.\d+)*)\s+", line)
        if match:
            return min(4, match.group(1).count(".") + 1)
        if re.match(r"^[IVXLCM]+\s+", line):
            return 1
        return 2 if len(line.split()) <= 7 else 1

    @classmethod
    def _split_into_sections(cls, text: str) -> list[dict[str, str | int]]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text or "") if p.strip()]
        if not paragraphs:
            return [{"title": "Document", "level": 1, "content": text or ""}]

        sections: list[dict[str, str | int]] = []
        current_title = "Document"
        current_level = 1
        current_body: list[str] = []

        def flush_current() -> None:
            body = "\n\n".join(current_body).strip()
            if current_title.strip() or body:
                sections.append(
                    {
                        "title": current_title.strip() or "Section",
                        "level": current_level,
                        "content": body,
                    }
                )

        for idx, para in enumerate(paragraphs):
            nxt = paragraphs[idx + 1] if idx + 1 < len(paragraphs) else None
            if cls._is_heading_candidate(para, nxt):
                flush_current()
                current_title = para.strip()
                current_level = cls._infer_heading_level(current_title)
                current_body = []
            else:
                current_body.append(para)

        flush_current()

        # Ensure no section is dropped.
        return [s for s in sections if str(s.get("title", "")).strip() or str(s.get("content", "")).strip()] or [
            {"title": "Document", "level": 1, "content": text or ""}
        ]

    @staticmethod
    def _estimate_section_summary_words(source_words: int, global_max_words: int | None) -> int:
        target = max(80, min(380, int(source_words * 0.25)))
        if global_max_words is not None:
            target = min(target, max(60, global_max_words))
        return target

    @staticmethod
    def _post_process_summary(text: str) -> str:
        output = (text or "").strip()
        output = re.sub(r"\s+", " ", output)
        output = re.sub(r"\s+([,.;:!?])", r"\1", output)
        return output.strip()

    @staticmethod
    def _render_structured_summary(sections: list[dict[str, str | int]]) -> str:
        rendered_parts: list[str] = []
        for section in sections:
            title = str(section.get("title") or "Section").strip()
            level = int(section.get("level") or 1)
            summary = str(section.get("summary") or "").strip()
            heading_prefix = "#" * max(1, min(level, 4))
            rendered_parts.append(f"{heading_prefix} {title}\n→ {summary}")
        return "\n\n".join(rendered_parts).strip()
