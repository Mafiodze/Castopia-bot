"""Text presentation helpers shared by the Telegram and Discord adapters."""

from __future__ import annotations

import html
import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
_DISCORD_MARKDOWN_RE = re.compile(r"([\\`*_{}\[\]<>])")


def excerpt(text: str, query: str, *, limit: int = 280) -> str:
    """Return a readable excerpt near the first sentence matching the query."""
    if limit <= 1:
        raise ValueError("limit must be greater than 1")

    normalized_text = _WHITESPACE_RE.sub(" ", text).strip()
    if not normalized_text:
        return "Описание на странице не найдено."

    needle = query.casefold().strip()
    sentences = _SENTENCE_SPLIT_RE.split(normalized_text)
    selected = next(
        (
            sentence
            for sentence in sentences
            if needle and needle in sentence.casefold()
        ),
        sentences[0],
    )

    if len(selected) <= limit:
        return selected

    clipped = selected[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;: ")
    return f"{clipped}…"


def highlight_html(text: str, query: str) -> str:
    """Escape Telegram HTML and safely highlight each query term."""
    escaped = html.escape(text)
    words = [word for word in query.split() if word]
    if not words:
        return escaped

    escaped_words = [html.escape(word) for word in words]
    pattern = re.compile(
        "|".join(re.escape(word) for word in escaped_words),
        re.IGNORECASE,
    )
    return pattern.sub(
        lambda match: f"<b>{match.group(0)}</b>",
        escaped,
    )


def escape_discord(text: str) -> str:
    """Escape Markdown-significant characters before putting text in an embed."""
    return _DISCORD_MARKDOWN_RE.sub(r"\1", text)