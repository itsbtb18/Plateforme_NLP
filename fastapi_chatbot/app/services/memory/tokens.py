"""
Token estimation utility.

Extracted from session_service to be reusable across the codebase.
"""


def estimate_tokens(text: str) -> int:
    """Fast heuristic token count (approx 1 token per 4 chars for Latin, 1:2 for Arabic)."""
    if not text:
        return 0
    return max(1, len(text) // 4)
