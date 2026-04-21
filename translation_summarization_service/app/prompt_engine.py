class PromptEngine:
    @staticmethod
    def _inject_text_chunk(prompt_template: str, text: str) -> str:
        return str(prompt_template).replace("{TEXT_CHUNK}", text or "")

    @staticmethod
    def translation_prompt(*, text: str, source_language: str, target_language: str) -> str:
        source = (source_language or "").strip() or "auto"
        target = (target_language or "").strip() or "auto"
        prompt_template = (
            "You are a STRICT full-document translation engine for technical and academic text.\\n"
            f"Translate from {source} to {target}.\\n"
            "Critical rules (mandatory):\\n"
            "1) Translate 100% of the source text. Do not omit any word, sentence, clause, list item, caption, footnote, or note.\\n"
            "2) NEVER summarize, shorten, paraphrase globally, or provide condensed output.\\n"
            "3) Preserve exact document order and structure: headings, paragraphs, bullets, numbering, and section sequence.\\n"
            "4) Preserve line alignment: keep the same line/paragraph boundaries whenever possible.\\n"
            "5) For each non-empty source line, output one corresponding translated line in the same order.\\n"
            "6) Keep technical terms, product names, APIs, class/function names, acronyms, and identifiers unchanged.\\n"
            "7) Preserve punctuation, symbols, numbers, units, references, URLs, and code-like fragments.\\n"
            "8) Do not add comments, notes, explanations, or metadata.\\n"
            "Output rules:\\n"
            "- Return ONLY the translated text.\\n"
            "- No intro, no outro, no title, no 'summary'.\\n"
            "- If an element should not be translated (e.g., code/identifier), keep it exactly as-is.\\n\\n"
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
                "- No headings, no bullets, no metadata, no prefatory phrases.\n"
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
            "# Executive Summary\\n"
            "(2-3 well-developed paragraphs)\\n\\n"
            "# Section Summaries\\n"
            "- Section 1: 1-2 paragraphs\\n"
            "- Section 2: 1-2 paragraphs\\n"
            "- Section 3: 1-2 paragraphs\\n"
            "(Add as many sections as needed to cover the whole document)\\n\\n"
            "# Key Points\\n"
            "- ...\\n"
            "- ...\\n\\n"
            "# Key Conclusions\\n"
            "- ...\\n"
            "- ...\\n"
            "Length guidance:\\n"
            "- Respect max_words when provided.\\n"
            "- If max_words is auto, choose a balanced length proportionate to source size, roughly 45-55% of the source when feasible.\\n"
            "- Return only the final formatted summary.\\n\\n"
            "Source text:\\n{TEXT_CHUNK}"
        )
        return PromptEngine._inject_text_chunk(prompt_template, text)
