import asyncio
import logging
from typing import List, Tuple
from urllib.parse import urljoin
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
from aiocache import cached, Cache
from .constants import (
    BASE_URL, START_PAGE_URL, TAGS_URL,
    SYSTEM_TAGS, BASE_URL_MIRROR,
    START_PAGE_URL_MIRROR, TAGS_URL_MIRROR,
    HEADERS
)

def article_links_decorator(func) -> None:
    """Декоратор для получения ссылок на статьи с проверкой на системные теги.

    Args:
        func (_type_): Асинхронная функция для получения ссылок на статьи.
    """
    async def wrapper(*args, **kwargs) -> List[Tuple[str, str]]:
        """Обертка для асинхронной функции.

        Returns:
            _type_: Результат выполнения асинхронной функции.
        """
        return await func(*args, **kwargs)
    return wrapper

class WikiScraper():
    """Класс для парсинга статей на Castopia Wiki.
    """
    def __init__(self, bot, base_url: str, start_page_url: str, tags_url: str,
                 max_concurrent_requests: int = 5) -> None:
        """Инициализация класса.

        Args:
            base_url (str):
            start_page_url (str):
            tags_url (str):
            headers (dict):
            max_concurrent_requests (int, optional): Defaults to 5.
        """
        self.base_url = base_url
        self.start_page_url = start_page_url
        self.tags_url = tags_url
        self.headers = HEADERS

        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.system_tags = SYSTEM_TAGS
        self.bot = bot

    def update_scraper_urls(self, pref: str) -> None:
        """Обновляет URL-адреса в WikiScraper в зависимости от настроек пользователя.

        Args:
            pref (str): Настройки пользователя (викидот или зеркало).
        """
        mirror = pref == "зеркало"
        self.base_url = BASE_URL_MIRROR if mirror else BASE_URL
        self.start_page_url = START_PAGE_URL_MIRROR if mirror else START_PAGE_URL
        self.tags_url = TAGS_URL_MIRROR if mirror else TAGS_URL

    @cached(ttl=300, key_builder=lambda f, self, url, *a, **k: url, cache=Cache.MEMORY)
    async def fetch_html(self, url: str, session: aiohttp.ClientSession, retry: int = 3) -> str:
        """Загружает HTML-код страницы по URL.

        Args:
            url (str): URL страницы.
            session (aiohttp.ClientSession): Сессия aiohttp.
            retry (int, optional): Количество попыток. Defaults to 3.

        Raises:
            e: Ошибка при загрузке страницы.

        Returns:
            str: HTML-код страницы.
        """
        for attempt in range(retry):
            try:
                async with self.semaphore:
                    async with session.get(url, headers=self.headers) as response:
                        response.raise_for_status()
                        return await response.text()
            except aiohttp.ClientError as e:
                logging.error("Ошибка при загрузке %s (попытка %d): %s", url, attempt + 1, e)
                if attempt < retry - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise e
        return ""

    async def get_total_pages(self, session: aiohttp.ClientSession) -> int:
        """Получает количество страниц пагинации.

        Args:
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            int: Количество страниц пагинации.
        """
        html = await self.fetch_html(self.start_page_url, session)
        soup = BeautifulSoup(html, "lxml")
        span = soup.find("span", class_="pager-no")
        return int(span.text.split()[-1]) if span else 1
    
    async def parse_links(self, html: str) -> List[Tuple[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        if soup.find("div", id="side-bar"): soup.find("div", id="side-bar").decompose()
        links, box = [], soup.find("div", class_="list-pages-box")
        if not box: return links
        for a in box.find_all("a"):
            title = a.get_text(strip=True)
            if title.lower() != "edit" and (href := a.get("href")):
                links.append((title, urljoin(self.base_url, href)))
        return links

    @article_links_decorator
    async def get_article_links_from_page(self, page_url: str, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает ссылки на статьи со страницы.

        Args:
            page_url (str): URL страницы.
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        return await self.parse_links(await self.fetch_html(page_url, session))

    async def get_article_links_from_page_f(self, page_url: str, session: aiohttp.ClientSession):
        html = await self.fetch_html(page_url, session)
        soup = BeautifulSoup(html, "lxml")
        links = []
        if (box := soup.find("div", class_="list-pages-box")):
            for a in box.find_all("a"):
                title = a.get_text(strip=True)
                if title.lower() == "edit": continue
                href = a.get("href")
                if not href: continue
                full_url = urljoin(self.base_url, href)
                tags_html = await self.fetch_html(full_url, session)
                tags_soup = BeautifulSoup(tags_html, "lxml")
                tags = tags_soup.find("div", class_="page-tags")
                article_tags = {a.get_text(strip=True).lower() for a in tags.find_all("a")} if tags else set()
                if article_tags & self.system_tags: continue
                links.append((title, full_url))
        return links

    async def get_all_article_links_f(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает все ссылки на статьи. (фильтрует по системным тегам)

        Args:
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        return await self._get_all(session, self.get_article_links_from_page_f)
    
    async def get_all_article_links(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает все ссылки на статьи.

        Args:
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        return await self._get_all(session, self.get_article_links_from_page)
    
    async def _get_all(self, session, fetcher):
        pages = await self.get_total_pages(session)
        tasks = [fetcher(f"{self.base_url}/system:all-pages/p/{i}" if i > 1 else self.start_page_url, session)
                 for i in range(1, pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [link for r in results if not isinstance(r, Exception) for link in r]

    
class PageParsingCog(commands.Cog):
    """Класс для инициализации кога.

    Args:
        commands (_type_): Наследует от класса commands.Cogs.
    """
    def __init__(self, bot) -> None:
        self.bot = bot

async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(PageParsingCog(bot))
