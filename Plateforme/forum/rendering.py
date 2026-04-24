from __future__ import annotations

from django.utils.html import escape

try:
    import bleach
except ImportError:  # pragma: no cover - runtime fallback when optional dep is missing
    bleach = None

try:
    import mistune
except ImportError:  # pragma: no cover - runtime fallback when optional dep is missing
    mistune = None


# Markdown parser with fenced code block support.
_MARKDOWN = (
    mistune.create_markdown(plugins=["strikethrough", "table", "url"])
    if mistune is not None
    else None
)

# Allow a conservative subset of HTML after markdown conversion.
ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "blockquote",
    "hr",
    "a",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_message_markdown(content: str) -> str:
    """
    Convert markdown to sanitized HTML.

    Notes:
    - LaTeX delimiters ($...$ and $$...$$) are preserved in text output and
      rendered client-side by KaTeX auto-render.
    - Sanitization prevents script/event-handler injection.
    """
    raw = content or ""
    # Keep the app running even if bleach is not installed in the container.
    # We return escaped plain text instead of unsanitized markdown HTML.
    if bleach is None or _MARKDOWN is None:
        return escape(raw).replace("\n", "<br>")

    html = _MARKDOWN(raw)
    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return bleach.linkify(clean)
