import random
import re
import json
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .page_parsing import WikiScraper
from .settings import Settings
from .constants import SYSTEM_TAGS, BASE_URL, START_PAGE_URL, TAGS_URL
from .txt_processing import TextProcessing

router = Router()
wiki_scraper = WikiScraper(router, BASE_URL, START_PAGE_URL, TAGS_URL)

SEARCH_CACHE: dict[int, list[tuple[str,str,str]]] = {}
RESULTS_PER_PAGE = 5

def build_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    prev_p = max(1, page - 1)
    next_p = min(total_pages, page + 1)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"fs:{prev_p}"),
        InlineKeyboardButton(text="➡️ Вперед", callback_data=f"fs:{next_p}")
    ]])

def render_page(results: list[tuple[str,str,str]], page: int) -> str:
    total = len(results)
    total_pages = (total - 1) // RESULTS_PER_PAGE + 1
    start = (page - 1) * RESULTS_PER_PAGE
    chunk = results[start:start + RESULTS_PER_PAGE]

    lines = [f"<b>Результаты (страница {page}/{total_pages}):</b>"]
    for title, url, snippet in chunk:
        lines.append(f'• <a href="{url}">{title}</a>\n{snippet}')
    return "\n\n".join(lines)

class BotCommands:
    def __init__(self):
        router.message(Command("settings"))(self.cmd_settings)
        router.message(Command("help"))(self.cmd_help)
        router.message(Command("randompage"))(self.cmd_randompage)
        router.message(Command("tags"))(self.cmd_tags)
        router.message(Command("search"))(self.cmd_search)
        router.message(Command("fullsearch"))(self.cmd_fullsearch)

    async def cmd_settings(self, message: types.Message):
        value = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        if value.lower() not in {"викидот", "зеркало"}: return await message.answer("Неверное значение.")
        try:
            with open("user_settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
        data[str(message.from_user.id)] = value.lower()
        with open("user_settings.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        await message.answer(f"Настройки сохранены: {value.lower()}")

    async def cmd_help(self, message: types.Message):
        cmds = {
            "help": "Выдает список всех команд или описание конкретной команды.",
            "randompage": "Выводит случайную страницу с сайта.",
            "tags": "Ищет статьи по указанным тегам.",
            "search": "Ищет статью по названию.",
            "fullsearch": "Ищет статьи, содержащие указанный текст.",
            "settings": "Настраивает предпочтения пользователя (викидот или зеркало)."
        }
        text = message.text.split(maxsplit=1)
        if len(text) > 1 and text[1] in cmds:
            await message.answer(f"/{text[1]} — {cmds[text[1]]}")
        else:
            help_msg = "\n".join(f"/{key} — {value}" for key,value in cmds.items())
            await message.answer(f"Список команд:\n{help_msg}")

    async def cmd_randompage(self, message: types.Message):
        wiki_scraper.update_scraper_urls(Settings.get_user_setting(message.from_user.id))
        async with aiohttp.ClientSession() as session:
            links = await wiki_scraper.from_site_fS(session)
            links = [(title, url) for title, url in links if "draft:" not in url and "_" not in url]
            title, link = random.choice(links)
            html = await wiki_scraper.fetch_html(link, session)
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div", id="page-content")
        if content:
            for e in content.select("div, br"): e.decompose()
            desc = re.sub(r"\s+", " ", content.get_text(" ")).strip().split(".")[0]
        else: desc = "Содержимое не найдено."
        button = InlineKeyboardButton(text="Читать далее", url=link)
        kb = InlineKeyboardMarkup(inline_keyboard=[[button]])
        await message.answer(f"<b>{title}</b>\n{desc}", reply_markup=kb)

    async def cmd_tags(self, message: types.Message):
        wiki_scraper.update_scraper_urls(Settings.get_user_setting(message.from_user.id))
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return await message.answer("Укажи теги через пробел после команды.")
        tags_list = parts[1].split()
        tag_url = f"{TAGS_URL}/tag/{tags_list[0]}"
        async with aiohttp.ClientSession() as session:
            html = await wiki_scraper.fetch_html(tag_url, session)
            soup = BeautifulSoup(html, "lxml")
            articles = []
            for link in soup.select("#tagged-pages-list a"):
                title, href = link.get_text(strip=True), urljoin(BASE_URL, link["href"])
                page_html = await wiki_scraper.fetch_html(href, session)
                tags_soup = BeautifulSoup(page_html, "lxml")
                page_tags = {title.get_text(strip=True).lower() for title in tags_soup.select("div.page-tags a")}
                if set(tags_list).issubset(page_tags): articles.append((title, href, ""))
        if not articles: return await message.answer(f"По тегам {' '.join(tags_list)} ничего не найдено.")
        lines = "\n".join(f'• <a href="{href}">{title}</a>' for title, href, _ in articles)
        await message.answer(f"<b>Статьи по тегам {', '.join(tags_list)}:</b>\n{lines}")

    async def cmd_search(self, message: types.Message):
        wiki_scraper.update_scraper_urls(Settings.get_user_setting(message.from_user.id))
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return await message.answer("Укажи название после команды.")
        name = parts[1].strip().lower()
        async with aiohttp.ClientSession() as session:
            links = await wiki_scraper.from_site(session)
            match = next(((title, url) for title, url in links if re.fullmatch(re.escape(name), title.lower())), None)
            if not match: return await message.answer(f"Страница '{name}' не найдена.")
            title, url = match
            html = await wiki_scraper.fetch_html(url, session)
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div", id="page-content")
        if content:
            for e in content.select("div, br"): e.decompose()
            desc = re.sub(r"\s+", " ", content.get_text(" ")).strip().split(".")[0]
        else: desc = "Содержимое не найдено."
        btn = InlineKeyboardButton(text="Читать далее", url=url)
        kb = InlineKeyboardMarkup(inline_keyboard=[[btn]])
        await message.answer(f"<b>{title}</b>\n{desc}", reply_markup=kb)

    async def cmd_fullsearch(self, message: types.Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip(): return await message.answer("❗ Укажи текст для поиска: /fullsearch <текст>")
        query = parts[1].strip().lower()
        wiki_scraper.update_scraper_urls(Settings.get_user_setting(message.from_user.id))
        async with aiohttp.ClientSession() as session:
            links = await wiki_scraper.from_site(session)
            results = []
            for title, url in links:
                if "draft:" in url or "admin:" in url:
                    continue
                html = await wiki_scraper.fetch_html(url, session)
                soup = BeautifulSoup(html, "lxml")
                content = soup.find("div", id="page-content")
                if content:
                    for e in content.select("div.no-style, br"): e.decompose()
                    text = content.get_text(" ", strip=True)
                else: text = ""
                if query in text.lower():
                    snippet = TextProcessing.extract_sentence_telegram(text, query)
                    soup_tags = BeautifulSoup(await wiki_scraper.fetch_html(url, session), "lxml")
                    tags_div = soup_tags.find("div", class_="page-tags")
                    page_tags = {link.get_text(strip=True).lower() for link in tags_div.find_all("a")} if tags_div else set()
                    if page_tags & SYSTEM_TAGS: continue
                    results.append((title, url, snippet))
        if not results: return await message.answer(f"По запросу «{query}» ничего не найдено.")
        SEARCH_CACHE[message.chat.id] = results
        total_pages = (len(results)-1)//RESULTS_PER_PAGE + 1
        text = render_page(results, 1)
        kb = build_keyboard(1, total_pages)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

class PaginationHandler:
    def __init__(self):
        router.callback_query(F.data.startswith("fs:"))(self.handle)

    async def handle(self, callback: types.CallbackQuery):
        _, pg = callback.data.split(":", 1)
        page = int(pg)
        results = SEARCH_CACHE.get(callback.message.chat.id)
        if not results: return await callback.answer("Сессия истекла.", show_alert=True)

        total = (len(results)-1)//RESULTS_PER_PAGE + 1
        page = max(1, min(page, total))
        text = render_page(results, page)
        kb = build_keyboard(page, total)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
        except Exception as e:
            await callback.answer("Ошибка при редактировании сообщения.", show_alert=True)

BotCommands()
PaginationHandler()
