"""Telegram adapter for the public Castopia wiki client."""

from __future__ import annotations

import html
import logging
import secrets
from dataclasses import dataclass
from time import monotonic

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .page_parsing import Article, UpstreamAccessError, UpstreamUnavailableError, WikiClient, WikiError
from .txt_processing import excerpt, highlight_html

logger = logging.getLogger(__name__)
RESULTS_PER_PAGE = 5
SEARCH_TTL_SECONDS = 10 * 60


@dataclass(slots=True)
class _SearchState:
    owner_id: int
    results: list[Article]
    query: str
    expires_at: float


class _SearchStore:
    def __init__(self) -> None:
        self._items: dict[str, _SearchState] = {}

    def save(self, owner_id: int, results: list[Article], query: str) -> str:
        self._prune()
        token = secrets.token_urlsafe(6)
        self._items[token] = _SearchState(
            owner_id=owner_id,
            results=results,
            query=query,
            expires_at=monotonic() + SEARCH_TTL_SECONDS,
        )
        return token

    def get(self, token: str) -> _SearchState | None:
        state = self._items.get(token)
        if state is None or monotonic() >= state.expires_at:
            self._items.pop(token, None)
            return None
        return state

    def _prune(self) -> None:
        now = monotonic()
        for token in [key for key, state in self._items.items() if state.expires_at <= now]:
            del self._items[token]


def _argument(message: types.Message) -> str:
    return (message.text or "").partition(" ")[2].strip()


def _article_message(article: Article, query: str = "") -> str:
    description = excerpt(article.text, query or article.title, limit=700)
    return f"<b>{html.escape(article.title)}</b>\n{highlight_html(description, query)}"


def _article_keyboard(article: Article) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть статью", url=article.url)]
        ]
    )


def _search_keyboard(token: str, page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="← Назад", callback_data=f"s:{token}:{page - 1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="Вперёд →", callback_data=f"s:{token}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _render_search_page(results: list[Article], query: str, page: int) -> str:
    total_pages = max(1, (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
    first = (page - 1) * RESULTS_PER_PAGE
    lines = [f"<b>Результаты поиска — {page}/{total_pages}</b>"]
    for article in results[first : first + RESULTS_PER_PAGE]:
        title = html.escape(article.title)
        url = html.escape(article.url, quote=True)
        snippet = highlight_html(excerpt(article.text, query), query)
        lines.append(f"• <a href=\"{url}\">{title}</a>\n{snippet}")
    return "\n\n".join(lines)[:4096]


async def _report_wiki_error(message: types.Message, error: Exception) -> None:
    if isinstance(error, UpstreamAccessError):
        await message.answer(
            "Источник запретил автоматический доступ. Для него нужен официальный API "
            "или разрешение владельца сайта."
        )
        return
    if isinstance(error, UpstreamUnavailableError):
        await message.answer("Источник временно недоступен. Попробуйте немного позже.")
        return
    logger.exception("Unexpected Telegram command error", exc_info=error)
    await message.answer("Не удалось обработать команду. Попробуйте ещё раз позже.")


def create_router(wiki: WikiClient) -> Router:
    """Create a router bound to one shared, long-lived wiki client."""
    router = Router(name="castopia")
    searches = _SearchStore()

    @router.message(Command("help", "start"))
    async def help_command(message: types.Message) -> None:
        await message.answer(
            "<b>Castopia</b> — быстрый поиск по публичной вики.\n\n"
            "/search &lt;название&gt; — найти статью по названию\n"
            "/fullsearch &lt;текст&gt; — поиск по содержимому\n"
            "/tags &lt;тег&gt; [тег…] — статьи с тегами\n"
            "/randompage — случайная статья\n\n"
            "Поиск использует открытые страницы источника и не обходит его ограничения."
        )

    @router.message(Command("randompage"))
    async def random_page(message: types.Message) -> None:
        try:
            article = await wiki.random_article()
            if article is None:
                await message.answer("Не нашёл подходящую публичную статью.")
            else:
                await message.answer(_article_message(article), reply_markup=_article_keyboard(article))
        except WikiError as error:
            await _report_wiki_error(message, error)

    @router.message(Command("search"))
    async def search_title(message: types.Message) -> None:
        query = _argument(message)
        if not query:
            await message.answer("Укажите название: <code>/search название статьи</code>")
            return
        try:
            article = await wiki.find_by_title(query)
            if article is None:
                await message.answer(f"Статья «{html.escape(query)}» не найдена.")
            else:
                await message.answer(_article_message(article, query), reply_markup=_article_keyboard(article))
        except WikiError as error:
            await _report_wiki_error(message, error)

    @router.message(Command("tags"))
    async def search_tags(message: types.Message) -> None:
        tags = _argument(message).split()
        if not tags:
            await message.answer("Укажите хотя бы один тег: <code>/tags тег1 тег2</code>")
            return
        try:
            articles = await wiki.find_by_tags(tags)
            if not articles:
                await message.answer("По этим тегам ничего не найдено.")
                return
            lines = [f"<b>Статьи с тегами: {html.escape(', '.join(tags))}</b>"]
            for article in articles[:30]:
                lines.append(
                    f"• <a href=\"{html.escape(article.url, quote=True)}\">"
                    f"{html.escape(article.title)}</a>"
                )
            await message.answer("\n".join(lines)[:4096])
        except WikiError as error:
            await _report_wiki_error(message, error)

    @router.message(Command("fullsearch"))
    async def search_content(message: types.Message) -> None:
        query = _argument(message)
        if not query:
            await message.answer("Укажите текст: <code>/fullsearch поисковый запрос</code>")
            return
        try:
            await message.bot.send_chat_action(message.chat.id, "typing")
            results = await wiki.search_content(query)
            if not results:
                await message.answer(f"По запросу «{html.escape(query)}» ничего не найдено.")
                return
            token = searches.save(message.from_user.id, results, query)
            total_pages = (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
            await message.answer(
                _render_search_page(results, query, 1),
                reply_markup=_search_keyboard(token, 1, total_pages),
                disable_web_page_preview=True,
            )
        except WikiError as error:
            await _report_wiki_error(message, error)

    @router.callback_query(F.data.startswith("s:"))
    async def paginate(callback: types.CallbackQuery) -> None:
        try:
            _, token, raw_page = (callback.data or "").split(":", 2)
            page = int(raw_page)
        except (TypeError, ValueError):
            await callback.answer("Некорректная кнопка.", show_alert=True)
            return
        state = searches.get(token)
        if state is None:
            await callback.answer("Результаты поиска устарели. Запустите поиск заново.", show_alert=True)
            return
        if callback.from_user.id != state.owner_id:
            await callback.answer("Эти результаты принадлежат другому пользователю.", show_alert=True)
            return
        total_pages = max(1, (len(state.results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
        page = max(1, min(page, total_pages))
        try:
            assert callback.message is not None
            await callback.message.edit_text(
                _render_search_page(state.results, state.query, page),
                reply_markup=_search_keyboard(token, page, total_pages),
                disable_web_page_preview=True,
            )
            await callback.answer()
        except Exception:
            logger.exception("Unable to edit Telegram search result")
            await callback.answer("Не удалось обновить результаты.", show_alert=True)

    return router
