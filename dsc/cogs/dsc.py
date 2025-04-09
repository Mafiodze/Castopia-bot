import asyncio
import aiohttp
import discord
import json
import random
import re
from typing import List, Tuple
from .page_parsing import WikiScraper
from .settings import Settings
from .constants import FOOTER_TEXT, SYSTEM_TAGS, BASE_URL, START_PAGE_URL, TAGS_URL, HEADERS
from .txt_processing import TextProcessing
from discord.ext import commands
from discord.ui import Button, View
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class SearchResultsView(View):
    def __init__(self, results: List[Tuple[int, str, str, str]], ctx: commands.Context, footer_text: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.results = results
        self.ctx = ctx
        self.footer_text = footer_text
        self.results_per_page = 5
        self.page = 1
        self.total_pages = (len(results) - 1) // self.results_per_page + 1

    def create_embed(self) -> discord.Embed:
        start, end = (self.page - 1) * 5, self.page * 5
        embed_pages_list = "\n".join([f"### [{t}]({u})\nСовпадений: {s}\n{sn}" for s, t, u, sn in self.results[start:end]])
        description = f"Найдено страниц: {len(self.results)}, показано топ-5, страница {self.page}/{self.total_pages}.\n{embed_pages_list}"
        embed = discord.Embed(title="Результаты поиска по отрывку", description=description, color=discord.Color.dark_red())
        embed.set_footer(text=self.footer_text)
        embed.timestamp = self.ctx.message.created_at
        return embed

    async def update_message(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = (self.page <= 1 if child.custom_id == "previous_page" else self.page >= self.total_pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary, custom_id="previous_page")
    async def previous_page(self, interaction, _):
        if self.page > 1: self.page -= 1; await self.update_message(interaction)
        else: await interaction.response.send_message("Это первая страница.", ephemeral=True)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_page(self, interaction, _):
        if self.page < self.total_pages: self.page += 1; await self.update_message(interaction)
        else: await interaction.response.send_message("Это последняя страница.", ephemeral=True)

class DscCog(commands.Cog):
    """Класс для работы с ботом.

    Args:
        commands (_type_): Класс для работы с командами.
        WikiScraper (_type_): Класс для парсинга статей на Castopia Wiki.
    """
    def __init__(self, bot: commands.Bot) -> None:
        """Инициализация класса.

        Args:
            bot (commands.Bot): Экземпляр бота.
            base_url (str): Основная ссылка.
            start_page_url (str): Ссылка со списком всех страниц.
            tags_url (str): Ссылка с тегами.
            headers (dict): Заголовки.
            max_concurrent_requests (int): Максимальное кол-во запросов.
        """
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(5)
        self.scraper = WikiScraper(self.bot, BASE_URL, START_PAGE_URL, TAGS_URL)

    @commands.command(name="settings")
    async def user_settings(self, ctx: commands.Context, value: str) -> None:
        """Настройка бота для пользователя.

        Args:
            ctx (commands.Context): Контекст команды.
            value (str): Значение настройки.

        Returns:
            _type_: Сообщение о результате настройки.
        """
        if value.lower() not in {"викидот", "зеркало"}:
            return await ctx.send("Неверное значение.")
        try:
            with open("user_settings.json", "r", encoding="utf-8") as f:
                settings_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            settings_data = {}
        settings_data[str(ctx.author.id)] = value.lower()
        with open("user_settings.json", "w", encoding="utf-8") as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=4)
        await ctx.send(f"Настройки обновлены для {ctx.author.mention}: {value.lower()}")

    @commands.command(name="help")
    async def show_help(self, ctx: commands.Context, command: str = 0) -> None:
        """Показывает список всех команд или описание конкретной команды.

        Args:
            ctx (commands.Context): Контекст команды.
            command (str, optional): Команда, которую ввел пользователь. По умолчанию 0.

        Returns:
            _type_: Сообщение с описанием команды.
        """
        desc = {
            "help": "Выдает список всех команд...",
            "randompage": "Случайная страница...",
            "tags": "Статьи по тегам...",
            "search": "Статьи по названию...",
            "fullsearch": "Статьи по содержанию...",
            "settings": "Настройки пользователя..."
        }
        if command:
            cmd = self.bot.get_command(command)
            if not cmd: return await ctx.send("Команда не найдена.")
            embed = discord.Embed(title=cmd.name, description=desc.get(cmd.name, "Описание отсутствует."), color=discord.Color.dark_red())
        else:
            embed = discord.Embed(title="Команды бота", description="\n".join([f"**{k}**: {v}" for k, v in desc.items()]), color=discord.Color.dark_red())
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)

    @commands.command(name="randompage")
    async def send_random_page(self, ctx: commands.Context) -> None:
        """Отправляет случайную страницу.

        Args:
            ctx (commands.Context): Контекст команды.
        """
        pref = Settings.get_user_setting(str(ctx.author.id))
        self.scraper.update_scraper_urls(pref)

        links = await self.scraper.get_all_article_links_f(self.session)
        links = [(t, u) for t, u in links if "draft:" not in u and "_" not in u]
        title, link = random.choice(links)
        text = await self.fetch_article_text(link)
        sent = text.split(".")[0].strip() + "." if text else "Содержимое не найдено."
        embed = discord.Embed(title=title, description=sent, url=link, color=discord.Color.dark_red())
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)

    @commands.command(name="tags")
    async def search_with_tags(self, ctx: commands.Context, *tags: str) -> None:
        """Поиск статей по тегам.

        Args:
            ctx (commands.Context): Контекст команды.
            *entered_tags (str): Теги для поиска.

        Returns:
            _type_: Сообщение с результатами поиска.

        Yields:
            _type_: Список статей по тегам.
        """
        if not tags: return await ctx.send("Укажите хотя бы один тег.")

        pref = Settings.get_user_setting(str(ctx.author.id))
        self.scraper.update_scraper_urls(pref)

        tag_url = f"{self.scraper.tags_url}/tag/{tags[0]}"
        html = await self.scraper.fetch_html(tag_url, self.session)
        soup = BeautifulSoup(html, "lxml")
        articles = []
        for a in soup.select("#tagged-pages-list a"):
            title, href = a.get_text(strip=True), urljoin(self.scraper.base_url, a['href'])
            text = await self.scraper.fetch_html(href, self.session)
            soup_tags = BeautifulSoup(text, "lxml")
            tags_div = soup_tags.find("div", class_="page-tags")
            page_tags = {t.get_text(strip=True).lower() for t in tags_div.find_all("a")} if tags_div else set()
            if set(tags).issubset(page_tags):
                articles.append(f"[{title}]({href})")
        if not articles: return await ctx.send(f"По тегу {', '.join(tags)} ничего не найдено.")
        embed = discord.Embed(title=f"Статьи с тегами {', '.join(tags)}", description="\n".join(articles), color=discord.Color.dark_red())
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)

    @commands.command(name="search")
    async def search_name(self, ctx: commands.Context, *, pagename: str) -> None:
        """Поиск статьи по названию.

        Args:
            ctx (commands.Context): Контекст команды.
            pagename (str): Название статьи.

        Returns:
            _type_: Сообщение с результатом поиска.
        """
        pref = Settings.get_user_setting(str(ctx.author.id))
        self.scraper.update_scraper_urls(pref)

        links = await self.scraper.get_all_article_links(self.session)
        pattern = re.compile(rf"\b{re.escape(pagename.lower())}\b")
        titles = [(t, u) for t, u in links if pattern.search(t.lower())]
        if not titles: return await ctx.send(f"Страница '{pagename}' не найдена.")
        t, u = titles[0]
        html = await self.scraper.fetch_html(u, self.session)
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div", id="page-content")
        if content:
            [e.decompose() for e in content.find_all("div", class_="no-style")]
            text = content.get_text(" ", strip=True)
        sent = text.split(".")[0].strip() + "." if text else "Содержимое не найдено."
        embed = discord.Embed(title=t, description=sent, url=u, color=discord.Color.dark_red())
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)

    @commands.command(name="fullsearch")
    async def search_excerpt(self, ctx: commands.Context, *, query: str) -> None:
        """Поиск статьи по отрывку.
    
        Args:
            ctx (commands.Context): Контекст команды.
            query (str): Отрывок для поиска.
    
        Returns:
            _type_: Сообщение с результатом поиска.
        """
        pref = Settings.get_user_setting(str(ctx.author.id))
        self.scraper.update_scraper_urls(pref)
    
        articles = await self.scraper.get_all_article_links(self.session)
        results = []
        for title, url in articles:
            if "draft:" in url: continue
            html = await self.scraper.fetch_html(url, self.session)
            soup = BeautifulSoup(html, "lxml")
            content = soup.find("div", id="page-content")
            if content:
                [e.decompose() for e in content.find_all("div", class_="no-style")]
                text = content.get_text(" ", strip=True)
            if query.lower() in text.lower():
                snippet = TextProcessing.extract_sentence(text, query)
                soup_tags = BeautifulSoup(await self.scraper.fetch_html(url, self.session), "lxml")
                tags_div = soup_tags.find("div", class_="page-tags")
                page_tags = {a.get_text(strip=True).lower() for a in tags_div.find_all("a")} if tags_div else set()
                if SYSTEM_TAGS & page_tags: continue
                results.append((text.lower().count(query.lower()), title, url, snippet))
        if not results: return await ctx.send("По заданному отрывку ничего не найдено.")
    
        results.sort(key=lambda x: x[0], reverse=True)
    
        view = SearchResultsView(results, ctx, FOOTER_TEXT)
        await ctx.send(embed=view.create_embed(), view=view)

async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(DscCog(bot))
