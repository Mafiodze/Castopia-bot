"""Presentation helpers shared by the Telegram and Discord adapters."""

from __future__ import annotations

import html
import re


def excerpt(text: str, query: str, *, limit: int = 280) -> str:
    """Return a readable, bounded excerpt around the first matching sentence."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "Описание на странице не найдено."
    needle = query.casefold().strip()
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    selected = next((s for s in sentences if needle and needle in s.casefold()), sentences[0])
    if len(selected) <= limit:
        return selected
    clipped = selected[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;: ")
    return f"{clipped}…"


def highlight_html(text: str, query: str) -> str:
    """Escape Telegram HTML then highlight a user query without injecting markup."""
    escaped = html.escape(text)
    words = [word for word in query.split() if word]
    if not words:
        return escaped
    pattern = re.compile("|".join(re.escape(html.escape(word)) for word in words), re.IGNORECASE)
    return pattern.sub(lambda match: f"<b>{match.group(0)}</b>", escaped)


def escape_discord(text: str) -> str:
    """Prevent page text from changing the Markdown layout of a Discord embed."""
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", text)
