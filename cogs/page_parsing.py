"""Cached, bounded client for the public Castopia wiki.

The client intentionally does not bypass access controls. HTTP 401/403 responses
are surfaced to callers so access must be obtained through an official API or the
site owner's permission.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Generic, TypeVar
from urllib.parse import unquote, urljoin, urlsplit

import aiohttp
from bs4 import BeautifulSoup

from .constants import SYSTEM_TAGS, WikiConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


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
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float

    def is_fresh(self) -> bool:
        return monotonic() < self.expires_at


@dataclass(frozen=True, slots=True)
class _TagReference:
    identifier: str
    url: str


@dataclass(slots=True)
class _UrlLockEntry:
    lock: asyncio.Lock
    users: int = 0


class WikiClient:
    """Fetch and parse wiki content with bounded concurrency and TTL caches."""

    PAGE_CACHE_TTL = timedelta(minutes=10)
    LINK_CACHE_TTL = timedelta(minutes=5)
    SEARCH_CACHE_TTL = timedelta(minutes=5)
    REQUEST_ATTEMPTS = 3
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=4, sock_read=8)
    EDIT_LABELS = frozenset({"edit", "редактировать"})

    MAX_PAGE_CACHE_ENTRIES = 512
    MAX_ARTICLE_CACHE_ENTRIES = 512
    MAX_SEARCH_CACHE_ENTRIES = 64

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

        self._page_cache: dict[str, _CacheEntry[str]] = {}
        self._article_cache: dict[str, _CacheEntry[Article]] = {}
        self._search_cache: dict[str, _CacheEntry[list[Article]]] = {}

        self._url_locks: dict[str, _UrlLockEntry] = {}
        self._links_cache: _CacheEntry[list[tuple[str, str]]] | None = None
        self._tag_catalog_cache: _CacheEntry[
            dict[str, list[_TagReference]]
        ] | None = None

    async def start(self) -> None:
        """Create the shared HTTP session if it is not already open."""
        if self._session is not None and not self._session.closed:
            return

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
        """Close the shared HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _normalise_url(self, url: str) -> str:
        """Return an absolute URL and reject requests outside the wiki origin."""
        absolute = urljoin(f"{self.base_url}/", url)
        parsed = urlsplit(absolute)

        if (parsed.scheme, parsed.netloc) != self._origin:
            raise ValueError(
                "Refusing to request a URL outside the configured wiki origin"
            )

        return absolute

    @staticmethod
    def _is_edit_link(title: str, href: str) -> bool:
        """Return whether a link points to an edit control rather than an article."""
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

    @staticmethod
    def _prune_cache(
        cache: dict[str, _CacheEntry[T]],
        max_entries: int,
    ) -> None:
        """Drop expired entries and then oldest entries above the size cap."""
        now = monotonic()

        expired = [
            key
            for key, entry in cache.items()
            if entry.expires_at <= now
        ]

        for key in expired:
            cache.pop(key, None)

        overflow = len(cache) - max_entries

        if overflow > 0:
            for key in list(cache)[:overflow]:
                cache.pop(key, None)

    def _store_cache(
        self,
        cache: dict[str, _CacheEntry[T]],
        key: str,
        value: T,
        ttl: timedelta,
        max_entries: int,
    ) -> None:
        """Store a cache value and keep the cache bounded."""
        cache[key] = _CacheEntry(
            value,
            monotonic() + ttl.total_seconds(),
        )
        self._prune_cache(cache, max_entries)

    async def fetch_html(self, url: str) -> str:
        """Fetch one same-origin page using a short-lived response cache."""
        url = self._normalise_url(url)

        cached = self._page_cache.get(url)
        if cached and cached.is_fresh():
            logger.debug("wiki_fetch cache_hit=true")
            return cached.value

        lock_entry = self._url_locks.get(url)

        if lock_entry is None:
            lock_entry = _UrlLockEntry(asyncio.Lock())
            self._url_locks[url] = lock_entry

        lock_entry.users += 1

        try:
            async with lock_entry.lock:
                cached = self._page_cache.get(url)

                if cached and cached.is_fresh():
                    logger.debug("wiki_fetch cache_hit=true")
                    return cached.value

                html = await self._request_html(url)

                self._store_cache(
                    self._page_cache,
                    url,
                    html,
                    self.PAGE_CACHE_TTL,
                    self.MAX_PAGE_CACHE_ENTRIES,
                )

                logger.debug("wiki_fetch cache_hit=false")
                return html
        finally:
            lock_entry.users -= 1

            if lock_entry.users == 0:
                self._url_locks.pop(url, None)

    async def _request_html(self, url: str) -> str:
        """Fetch HTML with bounded concurrency, retries and structured errors."""
        await self.start()

        if self._session is None:
            raise UpstreamUnavailableError(
                "HTTP client session is unavailable."
            )

        last_error: Exception | None = None

        for attempt in range(1, self.REQUEST_ATTEMPTS + 1):
            try:
                started_at = monotonic()

                async with self._semaphore:
                    async with self._session.get(
                        url,
                        allow_redirects=True,
                    ) as response:
                        elapsed_ms = round(
                            (monotonic() - started_at) * 1000
                        )

                        logger.debug(
                            "wiki_request status=%s duration_ms=%s attempt=%s",
                            response.status,
                            elapsed_ms,
                            attempt,
                        )

                        if response.status in {401, 403}:
                            raise UpstreamAccessError(
                                "Источник не разрешает автоматический доступ. "
                                "Используйте официальный API или запросите "
                                "разрешение владельца сайта."
                            )

                        if response.status == 404:
                            raise UpstreamNotFoundError(
                                "Страница больше не существует в источнике."
                            )

                        if response.status == 429 or 500 <= response.status < 600:
                            if attempt == self.REQUEST_ATTEMPTS:
                                raise UpstreamUnavailableError(
                                    f"Источник временно недоступен "
                                    f"(HTTP {response.status})."
                                )

                            delay = self._retry_delay(response, attempt)

                        elif 400 <= response.status < 500:
                            raise UpstreamUnavailableError(
                                f"Источник отклонил запрос "
                                f"(HTTP {response.status})."
                            )

                        else:
                            return await response.text(errors="replace")

                await asyncio.sleep(delay)

            except (
                UpstreamAccessError,
                UpstreamNotFoundError,
                UpstreamUnavailableError,
            ):
                raise

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc

                logger.warning(
                    "wiki_request_failed attempt=%s error=%s",
                    attempt,
                    type(exc).__name__,
                )

                if attempt < self.REQUEST_ATTEMPTS:
                    delay = min(
                        0.5 * (2 ** (attempt - 1))
                        + random.random() / 4,
                        10.0,
                    )
                    await asyncio.sleep(delay)

        raise UpstreamUnavailableError(
            "Не удалось связаться с источником."
        ) from last_error

    @staticmethod
    def _retry_delay(
        response: aiohttp.ClientResponse,
        attempt: int,
    ) -> float:
        """Return a bounded retry delay, honoring a valid Retry-After header."""
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                logger.debug("wiki_retry_after_invalid")

        return min(
            0.75 * (2 ** (attempt - 1)) + random.random() / 4,
            10.0,
        )

    async def all_links(self) -> list[tuple[str, str]]:
        """Return de-duplicated article links from every all-pages listing page."""
        if self._links_cache and self._links_cache.is_fresh():
            return list(self._links_cache.value)

        first_page = await self.fetch_html(self.all_pages_url)
        soup = BeautifulSoup(first_page, "lxml")
        page_content = soup.select_one("#page-content")

        if page_content is None:
            raise UpstreamContentError(
                "Источник вернул страницу списка без блока #page-content. "
                "Структура сайта могла измениться."
            )

        if not page_content.select("div.list-pages-box"):
            raise UpstreamContentError(
                "Источник вернул страницу списка без блоков "
                ".list-pages-box. Структура сайта могла измениться."
            )

        total_pages = self._parse_total_pages(first_page)
        pages = [first_page]

        if total_pages > 1:
            page_urls = [
                f"{self.all_pages_url}/p/{number}"
                for number in range(2, total_pages + 1)
            ]
            pages.extend(await self._fetch_in_batches(page_urls))

        seen: set[str] = set()
        links: list[tuple[str, str]] = []

        for html in pages:
            for title, url in self._parse_list_links(html):
                if url in seen:
                    continue

                seen.add(url)
                links.append((title, url))

        if not links:
            raise UpstreamContentError(
                "Источник вернул страницы списка со структурой "
                ".list-pages-box, но валидных ссылок на статьи не найдено."
            )

        self._links_cache = _CacheEntry(
            links,
            monotonic() + self.LINK_CACHE_TTL.total_seconds(),
        )

        return list(links)

    async def _run_bounded(
        self,
        values: Iterable[T],
        operation: Callable[[T], Awaitable[R]],
        *,
        log_label: str,
    ) -> tuple[list[R | None], list[Exception]]:
        """Run an async operation with bounded workers while preserving input order."""
        items = list(values)

        if not items:
            return [], []

        results: list[R | None] = [None] * len(items)
        failures: list[Exception] = []
        pending = deque(enumerate(items))

        async def worker() -> None:
            while True:
                try:
                    index, value = pending.popleft()
                except IndexError:
                    return

                try:
                    results[index] = await operation(value)
                except Exception as exc:
                    failures.append(exc)
                    logger.debug(
                        "%s item_failed index=%s error=%s",
                        log_label,
                        index,
                        type(exc).__name__,
                    )

        worker_count = min(
            self.config.max_concurrent_requests,
            len(items),
        )

        await asyncio.gather(
            *(asyncio.create_task(worker()) for _ in range(worker_count))
        )

        return results, failures

    async def _fetch_in_batches(
        self,
        urls: Iterable[str],
    ) -> list[str]:
        """Fetch listing pages concurrently without exceeding the configured limit."""
        results, _ = await self._run_bounded(
            urls,
            self.fetch_html,
            log_label="wiki_fetch_batch",
        )

        return [
            page
            for page in results
            if page is not None
        ]

    @staticmethod
    def _parse_total_pages(html: str) -> int:
        soup = BeautifulSoup(html, "lxml")
        pager = soup.find("span", class_="pager-no")

        if not pager:
            return 1

        match = re.search(
            r"(\d+)\s*$",
            pager.get_text(" ", strip=True),
        )

        return max(1, int(match.group(1))) if match else 1

    def _parse_list_links(
        self,
        html: str,
    ) -> list[tuple[str, str]]:
        """Parse article links from all list-page boxes and omit edit controls."""
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
                    links.append(
                        (
                            title,
                            self._normalise_url(href),
                        )
                    )
                except ValueError:
                    logger.debug(
                        "wiki_link_skipped reason=off_origin"
                    )

        return links

    async def get_article(
        self,
        title: str,
        url: str,
    ) -> Article:
        """Fetch, clean and cache one article."""
        url = self._normalise_url(url)

        cached = self._article_cache.get(url)
        if cached and cached.is_fresh():
            return cached.value

        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div", id="page-content")

        if content is None:
            raise UpstreamContentError(
                "Источник вернул страницу без блока #page-content. "
                "Структура сайта могла измениться."
            )

        for element in content.select(
            "script, style, noscript, .no-style, "
            ".footnoteref, #side-bar"
        ):
            element.decompose()

        text = re.sub(
            r"\s+",
            " ",
            content.get_text(" ", strip=True),
        ).strip()

        if not text:
            raise UpstreamContentError(
                f"Страница '{title}' не содержит доступного текста. "
                "Возможно, это служебная страница."
            )

        tags = frozenset(
            self._tag_identifier(item)
            or item.get_text(" ", strip=True).casefold()
            for item in soup.select("div.page-tags a")
            if item.get_text(strip=True)
        )

        article = Article(
            title=title,
            url=url,
            text=text,
            tags=tags,
        )

        self._store_cache(
            self._article_cache,
            url,
            article,
            self.PAGE_CACHE_TTL,
            self.MAX_ARTICLE_CACHE_ENTRIES,
        )

        return article

    @staticmethod
    def _is_public_candidate(
        title: str,
        url: str,
    ) -> bool:
        value = f"{title} {url}".casefold()

        return (
            "draft:" not in value
            and "admin:" not in value
            and "/edit/" not in value
            and not value.endswith("/edit")
        )

    async def _get_articles_in_batches(
        self,
        candidates: Iterable[tuple[str, str]],
    ) -> list[Article]:
        """Fetch and parse articles concurrently with bounded workers."""
        values = list(candidates)

        if not values:
            return []

        async def fetch_article(
            item: tuple[str, str],
        ) -> Article:
            return await self.get_article(*item)

        results, failures = await self._run_bounded(
            values,
            fetch_article,
            log_label="wiki_article_batch",
        )

        articles = [
            article
            for article in results
            if article is not None
        ]

        if not articles and failures:
            first_error = failures[0]

            if isinstance(first_error, WikiError):
                raise first_error

            raise UpstreamUnavailableError(
                "Не удалось загрузить статьи из источника."
            ) from first_error

        return articles

    async def find_by_title(
        self,
        query: str,
    ) -> Article | None:
        """Find an article by exact title first, then by partial title match."""
        normalized = query.casefold().strip()

        if not normalized:
            return None

        candidates = [
            (title, url)
            for title, url in await self.all_links()
            if self._is_public_candidate(title, url)
        ]

        exact = next(
            (
                (title, url)
                for title, url in candidates
                if title.casefold() == normalized
            ),
            None,
        )

        if exact is None:
            exact = next(
                (
                    (title, url)
                    for title, url in candidates
                    if normalized in title.casefold()
                ),
                None,
            )

        if exact is None:
            return None

        try:
            return await self.get_article(*exact)
        except UpstreamNotFoundError:
            return None

    async def title_suggestions(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> list[str]:
        """Return up to ``limit`` public article titles matching a query."""
        normalized = query.casefold().strip()

        if not normalized:
            return []

        return [
            title
            for title, url in await self.all_links()
            if (
                self._is_public_candidate(title, url)
                and normalized in title.casefold()
            )
        ][: max(0, limit)]

    async def random_article(self) -> Article | None:
        """Return a random public article, skipping stale or system pages."""
        candidates = [
            item
            for item in await self.all_links()
            if self._is_public_candidate(*item)
        ]

        random.shuffle(candidates)

        for title, url in candidates[:12]:
            try:
                article = await self.get_article(title, url)
            except UpstreamNotFoundError:
                continue

            if article.text and not (article.tags & SYSTEM_TAGS):
                return article

        return None

    async def _tag_catalog(
        self,
    ) -> dict[str, list[_TagReference]]:
        if (
            self._tag_catalog_cache
            and self._tag_catalog_cache.is_fresh()
        ):
            return self._tag_catalog_cache.value

        html = await self.fetch_html(self.tags_url)
        soup = BeautifulSoup(html, "lxml")
        catalog: dict[str, list[_TagReference]] = {}

        for anchor in soup.select("a.tag[href]"):
            display_name = anchor.get_text(
                " ",
                strip=True,
            ).casefold()

            identifier = self._tag_identifier(anchor)

            if not display_name or not identifier:
                continue

            reference = _TagReference(
                identifier,
                self._normalise_url(anchor["href"]),
            )

            for key in {display_name, identifier}:
                catalog.setdefault(key, []).append(reference)

        if not catalog:
            raise UpstreamContentError(
                "Источник не вернул каталог тегов."
            )

        self._tag_catalog_cache = _CacheEntry(
            catalog,
            monotonic() + self.LINK_CACHE_TTL.total_seconds(),
        )

        return catalog

    async def _resolve_tags(
        self,
        tags: Iterable[str],
    ) -> list[_TagReference] | None:
        catalog = await self._tag_catalog()
        resolved: list[_TagReference] = []

        for raw_tag in tags:
            normalized = raw_tag.casefold().strip()
            candidates = catalog.get(normalized)

            if not candidates:
                return None

            resolved.append(candidates[0])

        return resolved

    async def find_by_tags(
        self,
        tags: Iterable[str],
    ) -> list[Article]:
        """Return public articles containing every requested tag."""
        raw_tags = [
            tag.strip()
            for tag in tags
            if tag.strip()
        ]

        if not raw_tags:
            return []

        references = await self._resolve_tags(raw_tags)

        if references is None:
            return []

        required = {
            reference.identifier
            for reference in references
        }

        html = await self.fetch_html(
            references[0].url
        )
        soup = BeautifulSoup(html, "lxml")
        scope = soup.select_one("#tagged-pages-list")

        if scope is None:
            raise UpstreamContentError(
                "Источник не вернул список страниц для выбранного "
                "тега. Структура сайта может измениться."
            )

        candidates: list[tuple[str, str]] = []

        for anchor in scope.select("a[href]"):
            title = anchor.get_text(" ", strip=True)
            href = anchor["href"]

            if not title or self._is_edit_link(title, href):
                continue

            try:
                candidates.append(
                    (
                        title,
                        self._normalise_url(href),
                    )
                )
            except ValueError:
                continue

        if not candidates:
            return []

        articles = await self._get_articles_in_batches(candidates)

        return [
            article
            for article in articles
            if (
                self._is_public_candidate(
                    article.title,
                    article.url,
                )
                and required.issubset(article.tags)
                and not (article.tags & SYSTEM_TAGS)
            )
        ]

    async def search_content(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[Article]:
        """Search public articles by text and return relevance-ranked results."""
        normalized = query.casefold().strip()

        if not normalized:
            return []

        result_limit = max(0, limit)

        cached = self._search_cache.get(normalized)
        if cached and cached.is_fresh():
            return list(cached.value)[:result_limit]

        async with self._full_search_lock:
            cached = self._search_cache.get(normalized)

            if cached and cached.is_fresh():
                return list(cached.value)[:result_limit]

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
                if (
                    normalized in article.text.casefold()
                    and not (article.tags & SYSTEM_TAGS)
                )
            ]

            def relevance(article: Article) -> int:
                score = article.text.casefold().count(normalized)

                if normalized in article.title.casefold():
                    score += 10

                return score

            found.sort(
                key=lambda article: (
                    -relevance(article),
                    article.title.casefold(),
                )
            )

            self._store_cache(
                self._search_cache,
                normalized,
                found,
                self.SEARCH_CACHE_TTL,
                self.MAX_SEARCH_CACHE_ENTRIES,
            )

            logger.info(
                "wiki_search cache_hit=false query_length=%s "
                "articles_loaded=%s result_count=%s duration_ms=%s",
                len(normalized),
                len(articles),
                len(found),
                round(
                    (monotonic() - started_at) * 1000
                ),
            )

            return found[:result_limit]