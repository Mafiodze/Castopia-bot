import os
import asyncio
import logging
import pickle
from typing import List, Tuple
from urllib.parse import urljoin
import aiohttp
from discord.ext import commands
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from .constants import (
    BASE_URL, START_PAGE_URL, TAGS_URL,
    SYSTEM_TAGS, BASE_URL_MIRROR,
    START_PAGE_URL_MIRROR, TAGS_URL_MIRROR,
    HEADERS
)

class WikiScraper:
    SITEMAP_CACHE_TTL = timedelta(minutes=1)

    def __init__(self, bot, base_url: str, start_page_url: str, tags_url: str,
                 max_concurrent_requests: int = 5) -> None:
        self.bot = bot
        self.base_url = base_url
        self.start_page_url = start_page_url
        self.tags_url = tags_url
        self.headers = HEADERS

        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.system_tags = SYSTEM_TAGS

        self.CACHE_FILE = "cache.pkl"
        self._cache = self._load_cache()

        self._sitemap: dict[str, datetime] = {}
        self._sitemap_last_fetch: datetime = datetime.min.replace(tzinfo=None)

    def _load_cache(self) -> dict[str, Tuple[str, str]]:
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logging.error("Не удалось загрузить кэш: %s", e)
        return {}

    def _save_cache(self) -> None:
        try:
            with open(self.CACHE_FILE, "wb") as f:
                pickle.dump(self._cache, f)
        except Exception as e:
            logging.error("Не удалось сохранить кэш: %s", e)

    def _iso_now(self) -> str:
        return datetime.utcnow().replace(tzinfo=None).isoformat()

    def format_timestamp(self, dt: datetime) -> str:
        return dt.replace(tzinfo=None).isoformat()

    def update_scraper_urls(self, pref: str) -> None:
        mirror = (pref == "зеркало")
        self.base_url = BASE_URL_MIRROR if mirror else BASE_URL
        self.start_page_url = START_PAGE_URL_MIRROR if mirror else START_PAGE_URL
        self.tags_url = TAGS_URL_MIRROR if mirror else TAGS_URL

        self._sitemap.clear()
        self._sitemap_last_fetch = datetime.min.replace(tzinfo=None)

    async def _fetch_sitemap(self, session: aiohttp.ClientSession) -> None:
        now = datetime.utcnow().replace(tzinfo=None)
        if now - self._sitemap_last_fetch < self.SITEMAP_CACHE_TTL: return
        sitemap_url = urljoin(self.base_url, '/sitemap.xml')
        try:
            async with session.get(sitemap_url, headers=self.headers) as resp:
                resp.raise_for_status()
                xml = await resp.text()
            soup = BeautifulSoup(xml, 'xml')
            new_map: dict[str, datetime] = {}
            for u in soup.find_all('url'):
                loc = u.find('loc')
                lastmod = u.find('lastmod')
                if not loc or not lastmod: continue
                try: lm = datetime.fromisoformat(lastmod.text.rstrip('Z'))
                except ValueError: continue
                if lm.tzinfo is not None: lm = lm.astimezone(timezone.utc).replace(tzinfo=None)
                new_map[loc.text] = lm
            self._sitemap = new_map
            self._sitemap_last_fetch = now
        except Exception as e: logging.warning("Не удалось обновить sitemap: %s", e)

    async def fetch_html(self, url: str, session: aiohttp.ClientSession, retry: int = 3) -> str:
        await self._fetch_sitemap(session)
        if url in self._cache:
            cached_stamp_str, cached_html = self._cache[url]
            try: cached_stamp = datetime.fromisoformat(cached_stamp_str)
            except ValueError: self._cache.pop(url, None)
            else:
                lastmod = self._sitemap.get(url)
                if lastmod and lastmod <= cached_stamp: return cached_html
                self._cache.pop(url, None)

        for attempt in range(1, retry + 1):
            try:
                async with self.semaphore:
                    async with session.get(url, headers=self.headers) as resp:
                        resp.raise_for_status()
                        html = await resp.text()
                soup = BeautifulSoup(html, 'lxml')
                info_div = soup.find('div', id='page-info')
                if info_div and (span := info_div.find('span')):
                    txt = span.get_text().split('(')[0].strip()
                    try:
                        dt = datetime.strptime(txt, "%H:%M %d %b %Y")
                        stamp = self.format_timestamp(dt)
                    except Exception: stamp = self._iso_now()
                else: stamp = self._iso_now()
                self._cache[url] = (stamp, html)
                self._save_cache()
                return html
            except aiohttp.ClientError as e:
                logging.error("Ошибка загрузки %s (попытка %d/%d): %s", url, attempt, retry, e)
                if attempt < retry:
                    await asyncio.sleep(2 ** (attempt - 1))
                else: raise
        return ""

    async def get_total_pages(self, session: aiohttp.ClientSession) -> int:
        html = await self.fetch_html(self.start_page_url, session)
        soup = BeautifulSoup(html, "lxml")
        span = soup.find("span", class_="pager-no")
        return int(span.text.split()[-1]) if span else 1

    async def parse_links(self, html: str) -> List[Tuple[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        if (sb := soup.find("div", id="side-bar")): sb.decompose()
        links: List[Tuple[str, str]] = []
        box = soup.find("div", class_="list-pages-box")
        if not box: return links
        for a in box.find_all("a"):
            if a.get_text(strip=True).lower() == "edit": continue
            href = a.get("href")
            if href: links.append((a.get_text(strip=True), urljoin(self.base_url, href)))
        return links

    async def get_links(self, page_url: str, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        return await self.parse_links(await self.fetch_html(page_url, session))

    async def get_links_f(self, page_url: str, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        html = await self.fetch_html(page_url, session)
        soup = BeautifulSoup(html, "lxml")
        if (sb := soup.find("div", id="side-bar")): sb.decompose()
        links: List[Tuple[str, str]] = []
        box = soup.find("div", class_="list-pages-box")
        if box:
            for a in box.find_all("a"):
                title = a.get_text(strip=True)
                if title.lower() == "edit":
                    continue
                href = a.get("href")
                if not href: continue
                full_url = urljoin(self.base_url, href)
                tags_html = await self.fetch_html(full_url, session)
                tags_soup = BeautifulSoup(tags_html, "lxml")
                tags_div = tags_soup.find("div", class_="page-tags")
                article_tags = {t.get_text(strip=True).lower() for t in tags_div.find_all("a")} if tags_div else set()
                if article_tags & self.system_tags: continue
                links.append((title, full_url))
        return links

    async def from_site(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        return await self._get_all(session, self.get_links)

    async def from_site_f(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        return await self._get_all(session, self.get_links_f)

    async def _get_all(self, session: aiohttp.ClientSession, fetcher) -> List[Tuple[str, str]]:
        pages = await self.get_total_pages(session)
        tasks = [fetcher(f"{self.base_url}/system:all-pages/p/{i}" if i > 1 else self.start_page_url, session)
                 for i in range(1, pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_links: List[Tuple[str, str]] = []
        for res in results:
            if isinstance(res, list):
                all_links.extend(res)
        return all_links

class PageParsingCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.wiki_scraper = WikiScraper(bot, BASE_URL, START_PAGE_URL, TAGS_URL)

async def setup(bot) -> None:
    await bot.add_cog(PageParsingCog(bot))
