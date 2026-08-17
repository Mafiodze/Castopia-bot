"""Hybrid Discord commands for the public Castopia wiki client."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Awaitable, Callable, cast

import discord
from discord import app_commands
from discord.ext import commands

from .constants import FOOTER_TEXT, load_wiki_config
from .page_parsing import (
    Article,
    UpstreamAccessError,
    UpstreamContentError,
    UpstreamNotFoundError,
    UpstreamUnavailableError,
    WikiClient,
    WikiError,
)
from .txt_processing import escape_discord, excerpt

logger = logging.getLogger(__name__)
RESULTS_PER_PAGE = 5
MAX_QUERY_LENGTH = 160
MAX_TAGS = 5


@dataclass(frozen=True, slots=True)
class _RateLimit:
    requests: int
    period_seconds: float


class _RateLimiter:
    """One in-memory limiter shared by prefix and slash command invocations."""

    def __init__(self, limits: dict[str, _RateLimit]) -> None:
        self._limits = limits
        self._uses: dict[tuple[int, str], deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def retry_after(self, user_id: int, command_name: str) -> float:
        limit = self._limits[command_name]
        now = monotonic()
        key = (user_id, command_name)
        async with self._lock:
            uses = self._uses[key]
            while uses and now - uses[0] >= limit.period_seconds:
                uses.popleft()
            if len(uses) >= limit.requests:
                return max(0.0, limit.period_seconds - (now - uses[0]))
            uses.append(now)
        return 0.0


def _article_embed(article: Article, query: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=article.title[:256],
        description=escape_discord(excerpt(article.text, query or article.title, limit=900)),
        url=article.url,
        colour=discord.Colour.dark_red(),
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


class SearchResultsView(discord.ui.View):
    def __init__(self, owner_id: int, results: list[Article], query: str) -> None:
        super().__init__(timeout=10 * 60)
        self.owner_id = owner_id
        self.results = results
        self.query = query
        self.page = 1
        self.message: discord.Message | discord.WebhookMessage | None = None
        self._update_buttons()

    @property
    def total_pages(self) -> int:
        return max(1, (len(self.results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)

    def _update_buttons(self) -> None:
        self.previous_page.disabled = self.page <= 1
        self.next_page.disabled = self.page >= self.total_pages

    def create_embed(self) -> discord.Embed:
        start = (self.page - 1) * RESULTS_PER_PAGE
        embed = discord.Embed(
            title="Результаты поиска",
            description=f"Найдено: {len(self.results)} • страница {self.page}/{self.total_pages}",
            colour=discord.Colour.dark_red(),
        )
        for article in self.results[start : start + RESULTS_PER_PAGE]:
            title = escape_discord(article.title)[:256]
            text = escape_discord(excerpt(article.text, self.query, limit=500))
            embed.add_field(
                name=title,
                value=f"[Открыть статью]({article.url})\n{text}",
                inline=False,
            )
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Эти результаты принадлежат другому пользователю.", ephemeral=True
        )
        return False

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="← Назад", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.page = max(1, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Вперёд →", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.page = min(self.total_pages, self.page + 1)
        await self._refresh(interaction)

    async def on_timeout(self) -> None:
        self.disable_all_items()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.debug("discord_search_view_timeout_edit_failed")


class DscCog(commands.Cog):
    """Prefix and slash commands backed by one bounded wiki client."""

    RATE_LIMITS = {
        "search": _RateLimit(3, 20),
        "tags": _RateLimit(2, 30),
        "randompage": _RateLimit(2, 20),
        "fullsearch": _RateLimit(1, 30),
    }

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.wiki = WikiClient(load_wiki_config())
        self.rate_limiter = _RateLimiter(self.RATE_LIMITS)

    async def cog_load(self) -> None:
        await self.wiki.start()

    async def cog_unload(self) -> None:
        await self.wiki.close()

    @staticmethod
    def _error_text(error: Exception) -> str:
        if isinstance(error, UpstreamAccessError):
            return (
                "Источник запретил автоматический доступ. Нужен официальный API "
                "или разрешение владельца сайта."
            )
        if isinstance(error, UpstreamContentError):
            return "Структура источника изменилась. Администратор уже получил диагностическую запись."
        if isinstance(error, UpstreamNotFoundError):
            return "Статья больше не существует в источнике."
        if isinstance(error, UpstreamUnavailableError):
            return "Источник временно недоступен. Попробуйте немного позже."
        if isinstance(error, WikiError):
            return "Не удалось получить данные из источника."
        return "Не удалось обработать команду. Попробуйте ещё раз позже."

    async def _send_error(self, ctx: commands.Context, error: Exception) -> None:
        if not isinstance(error, WikiError):
            logger.exception("discord_command_failed error=%s", type(error).__name__)
        await ctx.send(self._error_text(error))

    async def _prepare_command(self, ctx: commands.Context, command_name: str) -> bool:
        retry_after = await self.rate_limiter.retry_after(ctx.author.id, command_name)
        if retry_after:
            await ctx.send(f"Подождите {retry_after:.0f} с перед следующим запросом.")
            return False
        if ctx.interaction is not None:
            # A deferred interaction is acknowledged within Discord's three-second window.
            await ctx.defer(thinking=True)
        return True

    async def _invoke(
        self,
        ctx: commands.Context,
        command_name: str,
        operation: Callable[[], Awaitable[object]],
    ) -> tuple[bool, object | None]:
        if not await self._prepare_command(ctx, command_name):
            return False, None
        started_at = monotonic()
        try:
            if ctx.interaction is None:
                async with ctx.typing():
                    result = await operation()
            else:
                result = await operation()
            return True, result
        except Exception as error:
            await self._send_error(ctx, error)
            return False, None
        finally:
            logger.info(
                "discord_command command=%s mode=%s duration_ms=%s",
                command_name,
                "slash" if ctx.interaction is not None else "prefix",
                round((monotonic() - started_at) * 1000),
            )

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        original = getattr(error, "original", error)
        await self._send_error(ctx, original)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> bool:
        text = self._error_text(getattr(error, "original", error))
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
        return True

    @commands.hybrid_command(name="help", description="Показать команды Castopia")
    async def show_help(self, ctx: commands.Context) -> None:
        if ctx.interaction is not None:
            await ctx.defer(thinking=False)
        embed = discord.Embed(
            title="Castopia — команды",
            description=(
                "`.search <название>` или `/search` — найти статью по названию\n"
                "`.fullsearch <текст>` или `/fullsearch` — поиск по содержимому\n"
                "`.tags <тег> [тег…]` или `/tags` — статьи с тегами\n"
                "`.randompage` или `/randompage` — случайная статья\n\n"
                "Бот работает только с публичными страницами и не обходит ограничения источника."
            ),
            colour=discord.Colour.dark_red(),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="randompage", description="Показать случайную статью")
    async def random_page(self, ctx: commands.Context) -> None:
        ok, result = await self._invoke(ctx, "randompage", self.wiki.random_article)
        if not ok:
            return
        article = cast(Article | None, result)
        if article is None:
            await ctx.send("Не нашёл подходящую публичную статью.")
        else:
            await ctx.send(embed=_article_embed(article))

    @commands.hybrid_command(name="search", description="Найти статью по названию")
    @app_commands.describe(query="Название статьи")
    async def search_title(self, ctx: commands.Context, *, query: str = "") -> None:
        query = query.strip()
        if not query:
            await ctx.send("Укажите название: `.search название статьи` или `/search`.")
            return
        if len(query) > MAX_QUERY_LENGTH:
            await ctx.send(f"Запрос должен быть не длиннее {MAX_QUERY_LENGTH} символов.")
            return
        ok, result = await self._invoke(ctx, "search", lambda: self.wiki.find_by_title(query))
        if not ok:
            return
        article = cast(Article | None, result)
        if article is None:
            await ctx.send(f"Статья «{escape_discord(query)}» не найдена.")
        else:
            await ctx.send(embed=_article_embed(article, query))

    @search_title.autocomplete("query")
    async def search_title_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if len(current.strip()) < 2:
            return []
        try:
            suggestions = await asyncio.wait_for(
                self.wiki.title_suggestions(current), timeout=2.5
            )
        except (WikiError, asyncio.TimeoutError):
            return []
        return [
            app_commands.Choice(name=title[:100], value=title[:100])
            for title in suggestions[:25]
        ]

    @commands.hybrid_command(name="tags", description="Найти статьи с тегами")
    @app_commands.describe(tags="Теги через пробел")
    async def search_tags(self, ctx: commands.Context, *, tags: str = "") -> None:
        tag_values = tags.split()
        if not tag_values:
            await ctx.send("Укажите хотя бы один тег: `.tags тег1 тег2` или `/tags`.")
            return
        if len(tag_values) > MAX_TAGS:
            await ctx.send(f"Можно указать не более {MAX_TAGS} тегов.")
            return
        if any(len(tag) > MAX_QUERY_LENGTH for tag in tag_values):
            await ctx.send("Тег слишком длинный.")
            return
        ok, result = await self._invoke(ctx, "tags", lambda: self.wiki.find_by_tags(tag_values))
        if not ok:
            return
        articles = cast(list[Article], result)
        if not articles:
            await ctx.send("По этим тегам ничего не найдено.")
            return
        embed = discord.Embed(
            title=f"Статьи с тегами: {', '.join(tag_values)}"[:256],
            description=f"Найдено: {len(articles)}",
            colour=discord.Colour.dark_red(),
        )
        for article in articles[:20]:
            embed.add_field(
                name=escape_discord(article.title)[:256],
                value=f"[Открыть статью]({article.url})",
                inline=False,
            )
        embed.set_footer(text=FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="fullsearch", description="Искать текст во всех статьях")
    @app_commands.describe(query="Текст для поиска")
    async def search_content(self, ctx: commands.Context, *, query: str = "") -> None:
        query = query.strip()
        if not query:
            await ctx.send("Укажите текст: `.fullsearch запрос` или `/fullsearch`.")
            return
        if len(query) > MAX_QUERY_LENGTH:
            await ctx.send(f"Запрос должен быть не длиннее {MAX_QUERY_LENGTH} символов.")
            return
        ok, result = await self._invoke(ctx, "fullsearch", lambda: self.wiki.search_content(query))
        if not ok:
            return
        results = cast(list[Article], result)
        if not results:
            await ctx.send(f"По запросу «{escape_discord(query)}» ничего не найдено.")
            return
        view = SearchResultsView(ctx.author.id, results, query)
        view.message = await ctx.send(embed=view.create_embed(), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DscCog(bot))
