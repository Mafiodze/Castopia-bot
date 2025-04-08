import asyncio
import logging
from typing import List, Tuple
from urllib.parse import urljoin
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
from aiocache import cached, Cache
from .constants import BASE_URL, START_PAGE_URL, TAGS_URL, SYSTEM_TAGS, BASE_URL_MIRROR, START_PAGE_URL_MIRROR, TAGS_URL_MIRROR, HEADERS

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
        result = await func(*args, **kwargs)
        return result
    return wrapper

class WikiScraper():
    """Класс для парсинга статей на Castopia Wiki.
    """

    def __init__(self, bot, base_url: str, start_page_url: str, tags_url: str, headers: dict = HEADERS,
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
        self.headers = headers
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.system_tags = SYSTEM_TAGS
        self.bot = bot

    def update_scraper_urls(self, pref: str) -> None:
        """Обновляет URL-адреса в WikiScraper в зависимости от настроек пользователя.

        Args:
            pref (str): Настройки пользователя (викидот или зеркало).
        """
        if pref == "зеркало":
            self.base_url = BASE_URL_MIRROR
            self.start_page_url = START_PAGE_URL_MIRROR
            self.tags_url = TAGS_URL_MIRROR
        else:
            self.base_url = BASE_URL
            self.start_page_url = START_PAGE_URL
            self.tags_url = TAGS_URL

    @cached(
        ttl=300,
        key_builder=lambda f, self, url, *args, **kwargs: url,
        cache=Cache.MEMORY
    )
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
                        html = await response.text()
                        return html
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
        pagination_span = soup.find("span", class_="pager-no")
        try:
            total_pages = int(pagination_span.text.split()[-1])
        except Exception:
            total_pages = 1
        return total_pages

    @article_links_decorator
    async def get_article_links_from_page(self, page_url: str, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает ссылки на статьи со страницы.

        Args:
            page_url (str): URL страницы.
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        html = await self.fetch_html(page_url, session)
        soup = BeautifulSoup(html, "lxml")
        links: List[Tuple[str, str]] = []
        side_bar = soup.find("div", id="side-bar")
        if side_bar:
            side_bar.decompose()
        list_box = soup.find("div", class_="list-pages-box")
        if list_box:
            p_tag = list_box.find("p")
            if p_tag:
                for link in p_tag.find_all("a"):
                    title = link.get_text(strip=True)
                    if title.lower() == "edit":
                        continue
                    href = link.get("href")
                    if href:
                        full_url = urljoin(self.base_url, href)
                        links.append((title, full_url))
        return links

    async def get_article_links_from_page_f(self, page_url: str, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает ссылки на статьи со страницы. (фильтрует по системным тегам)

        Args:
            page_url (str): URL страницы.
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        html = await self.fetch_html(page_url, session)
        soup = BeautifulSoup(html, "lxml")
        links: List[Tuple[str, str]] = []
        side_bar = soup.find("div", id="side-bar")
        if side_bar:
            side_bar.decompose()
        list_box = soup.find("div", class_="list-pages-box")
        if list_box:
            p_tag = list_box.find("p")
            if p_tag:
                for link in p_tag.find_all("a"):
                    title = link.get_text(strip=True)
                    if title.lower() == "edit":
                        continue
                    href = link.get("href")
                    if href:
                        full_url = urljoin(self.base_url, href)
                        html_url = await self.fetch_html(full_url, session)
                        html_soup = BeautifulSoup(html_url, "lxml")
                        tags_div = html_soup.find("div", class_="page-tags")
                        article_tags = {a.get_text(strip=True).lower() for a in tags_div.find_all("a")} if tags_div else set()
                        if article_tags & self.system_tags:
                            continue
                        links.append((title, full_url))
        return links

    async def get_all_article_links_f(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает все ссылки на статьи. (фильтрует по системным тегам)

        Args:
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        total_pages = await self.get_total_pages(session)
        tasks = []
        for count in range(1, total_pages + 1):
            page_url = self.start_page_url if count == 1 else f"{self.base_url}/system:all-pages/p/{count}"
            tasks.append(self.get_article_links_from_page_f(page_url, session))
        pages_results = await asyncio.gather(*tasks, return_exceptions=True)
        all_links: List[Tuple[str, str]] = []
        for result in pages_results:
            if isinstance(result, Exception):
                logging.error("Ошибка при сборе ссылок: %s", result)
            else:
                all_links.extend(result)
        return all_links
    
    async def get_all_article_links(self, session: aiohttp.ClientSession) -> List[Tuple[str, str]]:
        """Получает все ссылки на статьи.

        Args:
            session (aiohttp.ClientSession): Сессия aiohttp.

        Returns:
            List[Tuple[str, str]]: Список кортежей (название статьи, URL).
        """
        total_pages = await self.get_total_pages(session)
        tasks = []
        for count in range(1, total_pages + 1):
            page_url = self.start_page_url if count == 1 else f"{self.base_url}/system:all-pages/p/{count}"
            tasks.append(self.get_article_links_from_page(page_url, session))
        pages_results = await asyncio.gather(*tasks, return_exceptions=True)
        all_links: List[Tuple[str, str]] = []
        for result in pages_results:
            if isinstance(result, Exception):
                logging.error("Ошибка при сборе ссылок: %s", result)
            else:
                all_links.extend(result)
        return all_links
    
class PageParsingCog(commands.Cog, WikiScraper):
    """Класс для инициализации кога.

    Args:
        commands (_type_): Наследует от класса commands.Cogs.
        WikiScraper (_type_): Наследует от класса WikiScraper.
    """
    def __init__(self, bot) -> None:
        self.bot = bot

async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(PageParsingCog(bot))
