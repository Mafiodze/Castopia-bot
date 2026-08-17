"""A polite, cached client for the public Castopia wiki.

The client deliberately does not attempt to evade access controls. A 401/403
response is reported to callers; access must be obtained through an official
API or the site owner's permission.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Iterable
from urllib.parse import unquote, urljoin, urlsplit

import aiohttp
from bs4 import BeautifulSoup

from .constants import SYSTEM_TAGS, WikiConfig

logger = logging.getLogger(__name__)


class WikiError(RuntimeError):
    """Base error for a public-wiki request."""


class UpstreamAccessError(WikiError):
    """The source disallows this automated request."""


class UpstreamUnavailableError(WikiError):
    """The source could not be reached reliably."""


class UpstreamNotFoundError(WikiError):
    """A page listed by the source no longer exists."""


class UpstreamContentError(WikiError):
    """The source HTML no longer matches the expected public wiki structure."""


@dataclass(frozen=True, slots=True)
class Article:
    title: str
    url: str
    text: str
    tags: frozenset[str]


@dataclass(slots=True)
class _CacheEntry:
    value: object
    expires_at: float

    def is_fresh(self) -> bool:
        return monotonic() < self.expires_at


@dataclass(frozen=True, slots=True)
class _TagReference:
    identifier: str
    url: str


class WikiClient:
    """Fetch and parse content with bounded concurrency and short-lived caches."""

    PAGE_CACHE_TTL = timedelta(minutes=10)
    LINK_CACHE_TTL = timedelta(minutes=5)
    SEARCH_CACHE_TTL = timedelta(minutes=5)
    REQUEST_ATTEMPTS = 3
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=4, sock_read=8)
    EDIT_LABELS = frozenset({"edit", "редактировать"})

    def __init__(self, config: WikiConfig) -> None:
        self.config = config
        self.base_url = config.base_url
        self.all_pages_url = config.all_pages_url
        self.tags_url = config.tags_url
        parsed_base_url = urlsplit(self.base_url)
        self._origin = (parsed_base_url.scheme, parsed_base_url.netloc)
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._full_search_lock = asyncio.Lock()
        self._page_cache: dict[str, _CacheEntry] = {}
        self._article_cache: dict[str, _CacheEntry] = {}
        self._search_cache: dict[str, _CacheEntry] = {}
        self._url_locks: dict[str, asyncio.Lock] = {}
        self._links_cache: _CacheEntry | None = None
        self._tag_catalog_cache: _CacheEntry | None = None

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.config.max_concurrent_requests,
                limit_per_host=self.config.max_concurrent_requests,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.REQUEST_TIMEOUT,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ru,en;q=0.8",
                },
                raise_for_status=False,
            )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _normalise_url(self, url: str) -> str:
        absolute = urljoin(f"{self.base_url}/", url)
        parsed = urlsplit(absolute)
        if (parsed.scheme, parsed.netloc) != self._origin:
            raise ValueError("Refusing to request a URL outside the configured wiki origin")
        return absolute

    @staticmethod
    def _is_edit_link(title: str, href: str) -> bool:
        path = urlsplit(href).path.casefold().rstrip("/")
        return (
            title.casefold() in WikiClient.EDIT_LABELS
            or "/edit/" in path
            or path.endswith("/edit")
        )

    @staticmethod
    def _tag_identifier(anchor: object) -> str:
        """Read Wikidot's full category:value tag from a tag-link href."""
        href = getattr(anchor, "get", lambda *_: None)("href")
        if not href:
            return ""
        path = urlsplit(href).path
        marker = "/tag/"
        if marker not in path:
            return ""
        return unquote(path.split(marker, 1)[1]).casefold().strip()

    async def fetch_html(self, url: str) -> str:
        """Fetch one same-origin page, using a short-lived response cache."""
        url = self._normalise_url(url)
        cached = self._page_cache.get(url)
        if cached and cached.is_fresh():
            logger.debug("wiki_fetch cache_hit=true url=%s", url)
            return str(cached.value)

        lock = self._url_locks.setdefault(url, asyncio.Lock())
        async with lock:
            cached = self._page_cache.get(url)
            if cached and cached.is_fresh():
                logger.debug("wiki_fetch cache_hit=true url=%s", url)
                return str(cached.value)
            html = await self._request_html(url)
            self._page_cache[url] = _CacheEntry(
                html, monotonic() + self.PAGE_CACHE_TTL.total_seconds()
            )
            logger.debug("wiki_fetch cache_hit=false url=%s", url)
            return html

    async def _request_html(self, url: str) -> str:
        await self.start()
        assert self._session is not None

        last_error: Exception | None = None
        for attempt in range(1, self.REQUEST_ATTEMPTS + 1):
            try:
                started_at = monotonic()
                async with self._semaphore:
                    async with self._session.get(url, allow_redirects=True) as response:
                        elapsed_ms = round((monotonic() - started_at) * 1000)
                        logger.debug(
                            "wiki_request status=%s duration_ms=%s attempt=%s url=%s",
                            response.status,
                            elapsed_ms,
                            attempt,
                            url,
                        )
                        if response.status in {401, 403}:
                            raise UpstreamAccessError(
                                "Источник не разрешает автоматический доступ. Используйте "
                                "официальный API или запросите разрешение владельца сайта."
                            )
                        if response.status == 429 or 500 <= response.status < 600:
                            if attempt == self.REQUEST_ATTEMPTS:
                                raise UpstreamUnavailableError(
                                    f"Источник временно недоступен (HTTP {response.status})."
                                )
                            delay = self._retry_delay(response, attempt)
                        elif response.status == 404:
                            raise UpstreamNotFoundError("Страница больше не существует в источнике.")
                        elif 400 <= response.status < 500:
                            raise UpstreamUnavailableError(
                                f"Источник отклонил запрос (HTTP {response.status})."
                            )
                        else:
                            return await response.text(errors="replace")
                await asyncio.sleep(delay)
            except (UpstreamAccessError, UpstreamUnavailableError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                logger.warning(
                    "wiki_request_failed attempt=%s url=%s error=%s",
                    attempt,
                    url,
                    type(exc).__name__,
                )
                if attempt < self.REQUEST_ATTEMPTS:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)) + random.random() / 4)

        raise UpstreamUnavailableError("Не удалось связаться с источником.") from last_error

    @staticmethod
    def _retry_delay(response: aiohttp.ClientResponse, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return min(0.75 * (2 ** (attempt - 1)) + random.random() / 4, 10.0)

    async def all_links(self) -> list[tuple[str, str]]:
        """Return de-duplicated article links from every all-pages listing page."""
        if self._links_cache and self._links_cache.is_fresh():
            logger.debug("wiki_links cache_hit=true")
            return list(self._links_cache.value)  # type: ignore[arg-type]

        first_page = await self.fetch_html(self.all_pages_url)
        total_pages = self._parse_total_pages(first_page)
        pages = [first_page]
        if total_pages > 1:
            page_urls = [
                f"{self.all_pages_url}/p/{number}" for number in range(2, total_pages + 1)
            ]
            pages.extend(await self._fetch_in_batches(page_urls))

        seen: set[str] = set()
        links: list[tuple[str, str]] = []
        for html in pages:
            for title, url in self._parse_list_links(html):
                if url not in seen:
                    seen.add(url)
                    links.append((title, url))
        if not links:
            raise UpstreamContentError(
                "Источник вернул страницу списка, но в ней не найдены ссылки на статьи."
            )

        self._links_cache = _CacheEntry(
            links, monotonic() + self.LINK_CACHE_TTL.total_seconds()
        )
        logger.info("wiki_links count=%s pages=%s cache_hit=false", len(links), total_pages)
        return list(links)

    async def _fetch_in_batches(self, urls: Iterable[str]) -> list[str]:
        """Fetch listing pages through a fixed worker pool, preserving order."""
        values = list(urls)
        pages: list[str | None] = [None] * len(values)
        pending = deque(enumerate(values))

        async def worker() -> None:
            while pending:
                index, url = pending.popleft()
                pages[index] = await self.fetch_html(url)

        workers = [
            asyncio.create_task(worker())
            for _ in range(min(self.config.max_concurrent_requests, len(values)))
        ]
        if workers:
            await asyncio.gather(*workers)
        return [page for page in pages if page is not None]

    @staticmethod
    def _parse_total_pages(html: str) -> int:
        soup = BeautifulSoup(html, "lxml")
        pager = soup.find("span", class_="pager-no")
        if not pager:
            return 1
        match = re.search(r"(\d+)\s*$", pager.get_text(" ", strip=True))
        return max(1, int(match.group(1))) if match else 1

    def _parse_list_links(self, html: str) -> list[tuple[str, str]]:
        """Parse all list-page boxes, ignoring empty controls and edit links."""
        soup = BeautifulSoup(html, "lxml")
        scope = soup.select_one("#page-content") or soup
        links: list[tuple[str, str]] = []
        for box in scope.select("div.list-pages-box"):
            for anchor in box.find_all("a", href=True):
                title = anchor.get_text(" ", strip=True)
                href = anchor["href"]
                if not title or self._is_edit_link(title, href):
                    continue
                try:
                    links.append((title, self._normalise_url(href)))
                except ValueError:
                    logger.warning("wiki_link_skipped reason=off_origin href=%s", href)
        return links

    async def get_article(self, title: str, url: str) -> Article:
        url = self._normalise_url(url)
        cached = self._article_cache.get(url)
        if cached and cached.is_fresh():
            logger.debug("wiki_article cache_hit=true url=%s", url)
            return cached.value  # type: ignore[return-value]

        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div", id="page-content")
        if content is None:
            raise UpstreamContentError(
                "Источник вернул страницу без блока содержимого статьи."
            )
        for element in content.select(
            "script, style, noscript, .no-style, .footnoteref, #side-bar"
        ):
            element.decompose()
        text = re.sub(r"\s+", " ", content.get_text(" ", strip=True)).strip()
        tags = frozenset(
            self._tag_identifier(item) or item.get_text(" ", strip=True).casefold()
            for item in soup.select("div.page-tags a")
            if item.get_text(strip=True)
        )
        article = Article(title=title, url=url, text=text, tags=tags)
        self._article_cache[url] = _CacheEntry(
            article, monotonic() + self.PAGE_CACHE_TTL.total_seconds()
        )
        logger.debug("wiki_article cache_hit=false url=%s", url)
        return article

    @staticmethod
    def _is_public_candidate(title: str, url: str) -> bool:
        value = f"{title} {url}".casefold()
        return "draft:" not in value and "admin:" not in value and "/edit/" not in value

    async def _get_articles_in_batches(
        self, candidates: Iterable[tuple[str, str]]
    ) -> list[Article]:
        values = list(candidates)
        articles: list[Article] = []
        failures: list[BaseException] = []
        pending = deque(values)

        async def worker() -> None:
            while pending:
                title, url = pending.popleft()
                try:
                    articles.append(await self.get_article(title, url))
                except Exception as error:
                    failures.append(error)
                    logger.warning("wiki_article_failed error=%s", type(error).__name__)

        workers = [
            asyncio.create_task(worker())
            for _ in range(min(self.config.max_concurrent_requests, len(values)))
        ]
        if workers:
            await asyncio.gather(*workers)
        if not articles and failures:
            first_error = failures[0]
            if isinstance(first_error, WikiError):
                raise first_error
            raise UpstreamUnavailableError("Не удалось загрузить статьи из источника.")
        return articles

    async def find_by_title(self, query: str) -> Article | None:
        normalized = query.casefold().strip()
        if not normalized:
            return None
        candidates = [
            (title, url)
            for title, url in await self.all_links()
            if self._is_public_candidate(title, url)
        ]
        exact = next(((t, u) for t, u in candidates if t.casefold() == normalized), None)
        if exact is None:
            partial = [(t, u) for t, u in candidates if normalized in t.casefold()]
            exact = partial[0] if partial else None
        if exact is None:
            return None
        try:
            return await self.get_article(*exact)
        except UpstreamNotFoundError:
            return None

    async def title_suggestions(self, query: str, *, limit: int = 25) -> list[str]:
        normalized = query.casefold().strip()
        if not normalized:
            return []
        return [
            title
            for title, url in await self.all_links()
            if self._is_public_candidate(title, url) and normalized in title.casefold()
        ][:limit]

    async def random_article(self) -> Article | None:
        candidates = [
            item for item in await self.all_links() if self._is_public_candidate(*item)
        ]
        random.shuffle(candidates)
        for title, url in candidates[:12]:
            try:
                article = await self.get_article(title, url)
            except UpstreamNotFoundError:
                logger.info("wiki_random_skipped reason=not_found url=%s", url)
                continue
            if article.text and not (article.tags & SYSTEM_TAGS):
                return article
        return None

    async def _tag_catalog(self) -> dict[str, list[_TagReference]]:
        if self._tag_catalog_cache and self._tag_catalog_cache.is_fresh():
            return self._tag_catalog_cache.value  # type: ignore[return-value]

        html = await self.fetch_html(self.tags_url)
        soup = BeautifulSoup(html, "lxml")
        catalog: dict[str, list[_TagReference]] = {}
        for anchor in soup.select("a.tag[href]"):
            display_name = anchor.get_text(" ", strip=True).casefold()
            identifier = self._tag_identifier(anchor)
            if not display_name or not identifier:
                continue
            reference = _TagReference(identifier, self._normalise_url(anchor["href"]))
            for key in {display_name, identifier}:
                catalog.setdefault(key, []).append(reference)
        if not catalog:
            raise UpstreamContentError("Источник не вернул каталог тегов.")
        self._tag_catalog_cache = _CacheEntry(
            catalog, monotonic() + self.LINK_CACHE_TTL.total_seconds()
        )
        return catalog

    async def _resolve_tags(self, tags: Iterable[str]) -> list[_TagReference] | None:
        catalog = await self._tag_catalog()
        resolved: list[_TagReference] = []
        for raw_tag in tags:
            candidates = catalog.get(raw_tag.casefold().strip())
            if not candidates:
                return None
            # A short visible tag can occur in several categories. The first
            # category is stable in the wiki's catalogue; an explicit
            # "category:tag" input always resolves exactly.
            resolved.append(candidates[0])
        return resolved

    async def find_by_tags(self, tags: Iterable[str]) -> list[Article]:
        raw_tags = [tag for tag in tags if tag.strip()]
        if not raw_tags:
            return []
        references = await self._resolve_tags(raw_tags)
        if references is None:
            return []
        required = {reference.identifier for reference in references}
        html = await self.fetch_html(references[0].url)
        soup = BeautifulSoup(html, "lxml")
        scope = soup.select_one("#tagged-pages-list")
        if scope is None:
            raise UpstreamContentError("Источник не вернул список страниц для выбранного тега.")
        candidates: list[tuple[str, str]] = []
        for anchor in scope.select("a[href]"):
            title = anchor.get_text(" ", strip=True)
            href = anchor["href"]
            if not title or self._is_edit_link(title, href):
                continue
            try:
                candidates.append((title, self._normalise_url(href)))
            except ValueError:
                continue
        articles = await self._get_articles_in_batches(candidates)
        return [
            article
            for article in articles
            if self._is_public_candidate(article.title, article.url)
            and required.issubset(article.tags)
            and not (article.tags & SYSTEM_TAGS)
        ]

    async def search_content(self, query: str, *, limit: int = 50) -> list[Article]:
        normalized = query.casefold().strip()
        if not normalized:
            return []
        cached = self._search_cache.get(normalized)
        if cached and cached.is_fresh():
            logger.debug("wiki_search cache_hit=true query_length=%s", len(normalized))
            return list(cached.value)[:limit]  # type: ignore[arg-type]

        async with self._full_search_lock:
            cached = self._search_cache.get(normalized)
            if cached and cached.is_fresh():
                logger.debug("wiki_search cache_hit=true query_length=%s", len(normalized))
                return list(cached.value)[:limit]  # type: ignore[arg-type]
            started_at = monotonic()
            candidates = [
                item
                for item in await self.all_links()
                if self._is_public_candidate(*item)
            ]
            articles = await self._get_articles_in_batches(candidates)
            found = [
                article
                for article in articles
                if normalized in article.text.casefold()
                and not (article.tags & SYSTEM_TAGS)
            ]
            found.sort(
                key=lambda item: (
                    item.text.casefold().count(normalized)
                    + 10 * (normalized in item.title.casefold()),
                    item.title.casefold(),
                ),
                reverse=True,
            )
            self._search_cache[normalized] = _CacheEntry(
                found, monotonic() + self.SEARCH_CACHE_TTL.total_seconds()
            )
            logger.info(
                "wiki_search cache_hit=false query_length=%s result_count=%s duration_ms=%s",
                len(normalized),
                len(found),
                round((monotonic() - started_at) * 1000),
            )
            return found[:limit]
