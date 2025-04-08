import asyncio
import aiohttp
import discord
import json
import logging
import random
from typing import Dict, List, Set, Tuple
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
        start = (self.page - 1) * self.results_per_page
        end = self.page * self.results_per_page
        page_results = self.results[start:end]
        embed_pages_list = "\n".join(
            [f"### [{title}]({url})\nСовпадений: {score}\n{snippet}" for score, title, url, snippet in page_results]
        )
        description = (
            f"Найдено страниц: {len(self.results)}, показано топ-5, страница {self.page}/{self.total_pages}.\n"
            f"{embed_pages_list}"
        )
        embed = discord.Embed(
            title="Результаты поиска по отрывку",
            description=description,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=self.footer_text)
        embed.timestamp = self.ctx.message.created_at
        return embed

    async def update_message(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, Button):
                if child.custom_id == "previous_page":
                    child.disabled = self.page <= 1
                elif child.custom_id == "next_page":
                    child.disabled = self.page >= self.total_pages
        new_embed = self.create_embed()
        await interaction.response.edit_message(embed=new_embed, view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary, custom_id="previous_page")
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.page > 1:
            self.page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("Это первая страница.", ephemeral=True)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages:
            self.page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("Это последняя страница.", ephemeral=True)

class DSC(commands.Cog, WikiScraper):
    """Класс для работы с ботом.

    Args:
        commands (_type_): Класс для работы с командами.
        WikiScraper (_type_): Класс для парсинга статей на Castopia Wiki.
    """
    def __init__(self, bot: commands.Bot, base_url: str, start_page_url: str, tags_url: str, headers: dict, max_concurrent_requests: int) -> None:
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
        self.base_url = base_url
        self.start_page_url = start_page_url
        self.tags_url = tags_url
        self.headers = headers
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.system_tags = SYSTEM_TAGS
        self.scraper = WikiScraper(BASE_URL, START_PAGE_URL, TAGS_URL, HEADERS)

    @commands.command(name="settings")
    async def user_settings(self, ctx: commands.Context, value: str) -> None:
        """Настройка бота для пользователя.

        Args:
            ctx (commands.Context): Контекст команды.
            value (str): Значение настройки.

        Returns:
            _type_: Сообщение о результате настройки.
        """
        valid_values = {"викидот", "зеркало"}
        if value.lower() not in valid_values:
            return await ctx.send("Неверное значение. Допустимые значения: викидот, зеркало.")
        user_id = str(ctx.author.id)
        try:
            with open("user_settings.json", "r", encoding="utf-8") as f:
                settings_data = json.load(f)
        except FileNotFoundError:
            settings_data = {}
        except json.JSONDecodeError:
            settings_data = {}
        settings_data[user_id] = value.lower()
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
        commands_list: List[str] = [command.name for command in self.bot.commands]
        command_desc_dict: Dict[str, str] = {
            "help": "Выдает список всех команд. Если указать название команды, то выдаст описание этой команды. Пример: `.help randompage`.",
            "randompage": "Выдает случайную страницу. Пример: `.randompage`.",
            "tags": "Выдает статьи с указанными тегами. Ограничений по количеству тегов нет, для сложных тегов используйте нижнее подчеркивание. Пример: `системный структура_сайта`.",
            "search": "Выдает статьи с указанным названием. Можно писать как и по номеру (например, ритуал 1), так и по названию (например, пиковая дама). Пример: `.search ритуал 1`.",
            "fullsearch": "Выдает статьи с указанным отрывком/ключевыми словами (одно предложение). Пример: `.fullsearch обряд` (выдаст страницы, где будет найдено это слово).",
            "settings": "Позволяет настраивать бота под пользователя. У пользователя по умолчанию стоит значение `викидот` Принимает значения: викидот, зеркало. Пример: `.settings зеркало`."
        }
        if command not in commands_list and command != 0:
            return await ctx.send("Команда не найдена.")
        if command in commands_list:
            command_obj = self.bot.get_command(command)
            embed = discord.Embed(
                title=command_obj.name,
                description=command_desc_dict.get(command_obj.name, "Описание отсутствует."),
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=FOOTER_TEXT)
            embed.timestamp = ctx.message.created_at
            return await ctx.send(embed=embed)
        if command == 0:
            embed = discord.Embed(
                title="Команды бота",
                description="Список всех команд бота",
                color=discord.Color.dark_red()
            )
            embed.set_author(name=self.bot.user.name,
                            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.add_field(name="help", value="Выдает список всех команд. Если указать название команды, то выдаст описание этой команды.", inline=False)
            embed.add_field(name="randompage", value="Выдает случайную страницу.", inline=False)
            embed.add_field(name="tags", value="Выдает статьи с указанными тегами.", inline=False)
            embed.add_field(name="search", value="Выдает статьи с указанным названием.", inline=False)
            embed.add_field(name="fullsearch", value="Выдает статьи с указанным отрывком/ключевыми словами (одно предложение).", inline=False)
            embed.add_field(name="settings", value="Позволяет настраивать бота под пользователя.", inline=False)
            embed.set_footer(text=FOOTER_TEXT)
            embed.timestamp = ctx.message.created_at
            await ctx.send(embed=embed)

    @commands.command(name="randompage")
    async def send_random_page(self, ctx: commands.Context) -> None:
        """Отправляет случайную страницу.

        Args:
            ctx (commands.Context): Контекст команды.
        """
        user_id = str(ctx.author.id)
        pref = Settings.get_user_setting(user_id)
        self.scraper.update_scraper_urls(pref)

        try:
            all_links: List[Tuple[str, str]] = await self.scraper.get_all_article_links_f(self.session)
        except Exception as e:
            logging.error("Ошибка при сборе ссылок: %s", e)
            await ctx.send("Не удалось собрать ссылки на статьи.")
            return
        if not all_links:
            await ctx.send("Не удалось собрать ссылки на статьи.")
            return
        for random_title, random_link in all_links:
            if "draft:" in random_link:
                all_links.remove((random_title, random_link))
            if "_" in random_link:
                all_links.remove((random_title, random_link))
        random_title, random_link = random.choice(all_links)
        try:
            article_html = await self.scraper.fetch_html(random_link, self.session)
            article_soup = BeautifulSoup(article_html, "lxml")
            content_div = article_soup.find("div", id="page-content")
            if content_div:
                for elem in content_div.find_all("div", class_="no-style"):
                    elem.decompose()
                article_text = content_div.get_text(" ", strip=True)
                first_sentence = article_text.split(".")[0].strip() + "."
            else:
                first_sentence = "Содержимое не найдено."
        except Exception as e:
            logging.error("Ошибка при получении статьи: %s", e)
            first_sentence = "Ошибка при получении статьи."
        embed = discord.Embed(
            title=random_title,
            description=first_sentence,
            color=discord.Color.dark_red()
        )
        embed.url = random_link
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed)

    @commands.command(name="tags")
    async def search_with_tags(self, ctx: commands.Context, *entered_tags: str) -> None:
        """Поиск статей по тегам.

        Args:
            ctx (commands.Context): Контекст команды.
            *entered_tags (str): Теги для поиска.

        Returns:
            _type_: Сообщение с результатами поиска.

        Yields:
            _type_: Список статей по тегам.
        """
        if not entered_tags:
            return await ctx.send("Укажите хотя бы один тег.")
        user_id = str(ctx.author.id)
        pref = Settings.get_user_setting(user_id)
        self.scraper.update_scraper_urls(pref)

        required_tags: Set[str] = {tag.lower() for tag in entered_tags}
        base_tag = list(required_tags)[0]
        tag_page_url = f"{self.scraper.tags_url}/tag/{base_tag}"
        try:
            tag_html = await self.scraper.fetch_html(tag_page_url, self.session)
        except Exception as e:
            logging.error("Ошибка загрузки страницы тегов: %s", e)
            return await ctx.send("Ошибка при получении данных по тегам.")
        tag_soup = BeautifulSoup(tag_html, "lxml")

        async def get_articles():
            tag_pages = tag_soup.find_all("div", class_="pages-list", id="tagged-pages-list")
            for page in tag_pages:
                for a in page.find_all("a"):
                    article_title = a.get_text(strip=True)
                    article_href = a.get("href")
                    article_url = urljoin(self.scraper.base_url, article_href)
                    try:
                        article_html = await self.scraper.fetch_html(article_url, self.session)
                        article_soup = BeautifulSoup(article_html, "lxml")
                        tags_div = article_soup.find("div", class_="page-tags")
                        article_tags = {a.get_text(strip=True).lower() for a in tags_div.find_all("a")} if tags_div else set()
                        if required_tags <= article_tags:
                            yield article_title, article_url
                    except Exception as e:
                        logging.error("Ошибка получения статьи по тегу: %s", e)
        articles_list = []
        async for article_title, article_url in get_articles():
            articles_list.append(f"[{article_title}]({article_url})")
    
        if not articles_list:
            logging.info("Ничего не найдено для тегов: %s", ', '.join(entered_tags))
            return await ctx.send(f"По тегу {', '.join(entered_tags)} ничего не найдено.")
    
        embed = discord.Embed(
            title=f"Статьи с тегами {', '.join(entered_tags)}",
            description="\n".join(articles_list),
            color=discord.Color.dark_red()
        )
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
        user_id = str(ctx.author.id)
        pref = Settings.get_user_setting(user_id)
        self.scraper.update_scraper_urls(pref)

        all_links = await self.scraper.get_all_article_links(self.session)
        if not all_links:
            return await ctx.send("Ошибка при поиске статьи")
        all_names: List[str] = []
        all_urls: List[str] = []
        for title, url in all_links:
            if "-" in title:
                parts = title.split("-")
                title1 = parts[0].strip()
                title2 = parts[1].strip().strip("«»")
                all_names.extend([title1, title2])
                all_urls.extend([url, url])
            else:
                all_names.append(title)
                all_urls.append(url)
        pagename_lower = pagename.lower()
        found_index = None
        for i, name in enumerate(all_names):
            if name.lower() == pagename_lower:
                found_index = i
                break
        if found_index is None:
            await ctx.send(f"Страница '{pagename}' не найдена.")
            logging.info("Страница '%s' не найдена. Пользователь: %s", pagename, ctx.message.author)
            return
        try:
            article_html = await self.scraper.fetch_html(all_urls[found_index], self.session)
            article_soup = BeautifulSoup(article_html, "lxml")
            content_div = article_soup.find("div", id="page-content")
            if content_div:
                for elem in content_div.find_all("div", class_="no-style"):
                    elem.decompose()
                article_text = content_div.get_text(" ", strip=True)
                first_sentence = article_text.split(".")[0].strip() + "."
            else:
                first_sentence = "Содержимое не найдено."
        except Exception as e:
            logging.error("Ошибка получения статьи: %s", e)
            first_sentence = "Ошибка при получении статьи."
        embed = discord.Embed(
            title=all_names[found_index],
            description=first_sentence,
            color=discord.Color.dark_red()
        )
        embed.url = all_urls[found_index]
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
        user_id = str(ctx.author.id)
        pref = Settings.get_user_setting(user_id)
        self.scraper.update_scraper_urls(pref)
    
        if not query:
            return await ctx.send("Укажите отрывок для поиска.")
    
        system_tags = {"компонент", "навигация", "поиск", "системный", "тест", "структура_сайта"}
        all_articles = await self.scraper.get_all_article_links(self.session)
        if not all_articles:
            return await ctx.send("Не удалось собрать ссылки на статьи.")
    
        results: List[Tuple[int, str, str, str]] = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
    
        for title, url in all_articles:
            try:
                if "draft:" in url:
                    continue
                article_html = await self.scraper.fetch_html(url, self.session)
                article_soup = BeautifulSoup(article_html, "lxml")
                content_div = article_soup.find("div", id="page-content")
                if not content_div:
                    continue
                for elem in content_div.find_all("div", class_="no-style"):
                    elem.decompose()
                for elem in content_div.find_all("a"):
                    href_text = elem.get_text(strip=True)
                    if "http" in href_text:
                        elem.decompose()
                    else:
                        elem.replace_with(href_text)
                text = content_div.get_text(" ", strip=True)
                text_lower = text.lower()
                snippet = TextProcessing.extract_sentence(text, query)
                if snippet:
                    score = text_lower.count(query_lower)
                else:
                    snippet = TextProcessing.trim_text(text, 300)
                    score = sum(1 for word in query_words if word in text_lower)
    
                tags_html = await self.scraper.fetch_html(urljoin(url, ""), self.session)
                tags_soup = BeautifulSoup(tags_html, "lxml")
                tags_div = tags_soup.find("div", class_="page-tags")
                article_tags = {a.get_text(strip=True).lower() for a in tags_div.find_all("a")} if tags_div else set()
                if system_tags & article_tags:
                    continue
                if score > 0:
                    results.append((score, title, url, snippet))
            except TypeError:
                pass
            except Exception as e:
                logging.error("Ошибка обработки статьи %s: %s", url, e)
    
        if not results:
            return await ctx.send("По заданному отрывку ничего не найдено.")
    
        results.sort(key=lambda x: x[0], reverse=True)
    
        view = SearchResultsView(results, ctx, FOOTER_TEXT)
        embed = view.create_embed()
    
        await ctx.send(embed=embed, view=view)

class DscCog(DSC):
    """Класс для инициализации кога.

    Args:
        DSC (_type_): Наследует от класса DSC
    """
    def __init__(self, bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.base_url = BASE_URL
        self.start_page_url = START_PAGE_URL
        self.tags_url = TAGS_URL
        self.headers = HEADERS
        self.semaphore = asyncio.Semaphore(5)
        self.system_tags = SYSTEM_TAGS
        self.scraper = WikiScraper(BASE_URL, START_PAGE_URL, TAGS_URL, HEADERS)

async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(DscCog(bot))
