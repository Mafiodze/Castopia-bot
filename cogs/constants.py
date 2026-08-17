"""Project-wide configuration for the Castopia bots."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


DEFAULT_WIKI_BASE_URL = "https://castopia.site"
DEFAULT_USER_AGENT = "CastopiaBot/2.0 (community reader; configure WIKI_USER_AGENT)"

# Pages bearing any of these tags are omitted from public random/search results.
SYSTEM_TAGS = frozenset(
    {
        "структура:компонент",
        "структура:навигация",
        "структура:поиск",
        "структура:системный",
        "структура:тест",
        "структура:структура_сайта",
    }
)

FOOTER_TEXT = "Содержимое распространяется по лицензии CC BY-SA 3.0"


class ConfigurationError(ValueError):
    """Raised when a required environment configuration value is invalid."""


@dataclass(frozen=True, slots=True)
class WikiConfig:
    """Validated, non-secret settings for the public wiki source."""

    base_url: str
    user_agent: str
    max_concurrent_requests: int

    @property
    def all_pages_url(self) -> str:
        return f"{self.base_url}/system:all-pages"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url}/system:page-tags"


def load_wiki_config() -> WikiConfig:
    """Load public wiki settings and reject malformed or unsafe source URLs."""
    raw_url = os.getenv("WIKI_BASE_URL", DEFAULT_WIKI_BASE_URL).strip().rstrip("/")
    parsed = urlsplit(raw_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "WIKI_BASE_URL must be an absolute HTTPS URL, for example https://castopia.site"
        )

    try:
        concurrency = int(os.getenv("WIKI_MAX_CONCURRENCY", "4"))
    except ValueError as exc:
        raise ConfigurationError("WIKI_MAX_CONCURRENCY must be an integer") from exc
    if not 1 <= concurrency <= 10:
        raise ConfigurationError("WIKI_MAX_CONCURRENCY must be between 1 and 10")

    user_agent = os.getenv("WIKI_USER_AGENT", DEFAULT_USER_AGENT).strip()
    if not user_agent:
        raise ConfigurationError("WIKI_USER_AGENT cannot be empty")

    return WikiConfig(
        base_url=raw_url,
        user_agent=user_agent,
        max_concurrent_requests=concurrency,
    )
