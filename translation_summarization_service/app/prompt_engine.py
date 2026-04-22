class PromptEngine:
    @staticmethod
    def _inject_text_chunk(prompt_template: str, text: str) -> str:
        return str(prompt_template).replace("{TEXT_CHUNK}", text or "")

    @staticmethod
    def translation_prompt(*, text: str, source_language: str, target_language: str) -> str:
        source = (source_language or "").strip() or "auto"
        target = (target_language or "").strip() or "auto"
        prompt_template = (
            "You are a STRICT full-document translation engine for technical and academic text.\n"
            f"Translate from {source} to {target}.\\n"
            "Critical rules (mandatory):\\n"
            "1) Translate 100% of the source text. Do not omit any word, sentence, clause, list item, caption, footnote, or note.\n"
            "2) NEVER summarize, shorten, paraphrase globally, or provide condensed output.\n"
            "3) Preserve the full document structure: headings, paragraphs, bullets, numbering, tables, captions, quotes, citations, and section order.\n"
            "4) Keep the output as a readable article-style translation, with natural paragraph flow and coherent sentence structure.\n"
            "5) If the target language is Arabic, write in natural RTL Arabic, keep paragraph boundaries clear, and make the result read like a professional article.\n"
            "6) Keep technical terms, product names, APIs, class/function names, acronyms, identifiers, and code-like fragments unchanged unless a standard translation is clearly required.\n"
            "7) Preserve punctuation, symbols, numbers, units, references, URLs, formulas, and code fragments exactly.\n"
            "8) If a source heading or label exists, translate it and keep it in the same relative position.\n"
            "9) Do not add comments, notes, explanations, summaries, or metadata.\n"
            "Output rules:\\n"
            "- Return ONLY the translated text.\\n"
            "- No intro, no outro, no title, no summary, and no extra commentary.\n"
            "- Keep paragraph breaks and section breaks wherever possible.\n"
            "- If an element should not be translated (e.g., code/identifier), keep it exactly as-is.\n\n"
            "Source text:\\n{TEXT_CHUNK}"
        )
        return PromptEngine._inject_text_chunk(prompt_template, text)

    @staticmethod
    def summarization_prompt(*, text: str, language: str, style: str, max_words: int | None) -> str:
        output_language = (language or "").strip() or "en"
        summary_style = (style or "").strip() or "professional"
        max_words_str = str(max_words) if max_words is not None else "auto"

        if summary_style.startswith("section::") or summary_style.startswith("section-final::"):
            prompt_template = (
                "You are a professional section summarizer.\n"
                f"Write the output in language={output_language}. style={summary_style}. max_words={max_words_str}.\n"
                "Mandatory rules:\n"
                "1) Summarize ONLY the provided section content.\n"
                "2) Do not reference other sections or the whole document.\n"
                "3) Keep technical terms, acronyms, identifiers, and proper names unchanged.\n"
                "4) Use professional reformulation (no copy-paste).\n"
                "5) Include main ideas and key points, with complete coverage in well-formed paragraphs.\n"
                "6) Keep length balanced: about 45-55% of source section when possible.\n"
                "Output format (strict):\n"
                "- Return 2 paragraphs when possible; 3 paragraphs max.\n"
                "- Add a short professional title before each paragraph.\n"
                "- Do not use labels like Part 1, Part 2, Section 1, or similar numbering.\n"
                "- Keep each paragraph focused on one idea and make the title reflect that idea.\n"
                "- No bullets, no metadata, no prefatory phrases.\n"
                "- No markdown.\n\n"
                "Section content:\n{TEXT_CHUNK}"
            )
            return PromptEngine._inject_text_chunk(prompt_template, text)

        prompt_template = (
            "You are an advanced professional summarization engine.\\n"
            f"Summarize in language={output_language}. style={summary_style}. max_words={max_words_str}.\\n"
            "Quality requirements (mandatory):\\n"
            "1) Write a clear, professional, well-structured summary with readable paragraphs.\\n"
            "2) Cover all major sections of the source. Provide one concise subsection summary per source section.\\n"
            "3) Highlight main ideas, important points, and key conclusions.\\n"
            "4) Keep balanced length: target about half of the source length when max_words allows it.\\n"
            "5) Use natural and fluent language.\\n"
            "6) Do not omit important information.\\n"
            "7) Reformulate professionally; do not copy large source blocks.\\n"
            "8) Do not invent facts not present in the source.\\n"
            "Output format (required):\\n"
            "- Write 2-4 paragraphs depending on source length.\\n"
            "- Put a short professional title before each paragraph.\\n"
            "- Do not use labels like Part 1, Part 2, Section 1, or similar numbering.\\n"
            "- Make each title specific to the paragraph that follows.\\n"
            "- Keep the output as clean prose, not a report with bullets or headings.\\n"
            "Length guidance:\\n"
            "- Respect max_words when provided.\\n"
            "- If max_words is auto, choose a balanced length proportionate to source size, roughly 45-55% of the source when feasible.\\n"
            "- Return only the final formatted summary.\\n\\n"
            "Source text:\\n{TEXT_CHUNK}"
        )
        return PromptEngine._inject_text_chunk(prompt_template, text)
