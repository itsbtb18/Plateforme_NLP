class PromptEngine:
    @staticmethod
    def translation_prompt(*, text: str, source_language: str, target_language: str) -> str:
        return (
            "You are a high-fidelity translation engine.\\n"
            f"Translate from {source_language} to {target_language}.\\n"
            "Preserve named entities and technical terms.\\n"
            "Return only translated text.\\n\\n"
            f"Source text:\\n{text}"
        )

    @staticmethod
    def summarization_prompt(*, text: str, language: str, style: str, max_words: int | None) -> str:
        max_words_str = str(max_words) if max_words is not None else "auto"
        return (
            "You are a grounded summarization engine.\\n"
            f"Summarize in language={language}. style={style}. max_words={max_words_str}.\\n"
            "Do not invent facts. Return only summary text.\\n\\n"
            f"Source text:\\n{text}"
        )
