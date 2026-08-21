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

from .page_parsing import (
    Article,
    UpstreamAccessError,
    UpstreamContentError,
    UpstreamNotFoundError,
    UpstreamUnavailableError,
    WikiClient,
    WikiError,
)
from .txt_processing import excerpt, highlight_html

logger = logging.getLogger(__name__)

RESULTS_PER_PAGE = 5
SEARCH_TTL_SECONDS = 10 * 60
MAX_QUERY_LENGTH = 160
MAX_TAGS = 5
MAX_TAG_RESULTS = 30


@dataclass(slots=True)
class _SearchState:
    owner_id: int
    results: list[Article]
    query: str
    expires_at: float

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class _SearchStore:
    """Short-lived in-memory storage for Telegram pagination state."""

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
        if state is None:
            return None

        if state.is_expired(monotonic()):
            self._items.pop(token, None)
            return None

        return state

    def _prune(self) -> None:
        now = monotonic()
        expired_tokens = [
            token
            for token, state in self._items.items()
            if state.is_expired(now)
        ]
        for token in expired_tokens:
            self._items.pop(token, None)


def _argument(message: types.Message) -> str:
    """Return the text after the Telegram command."""
    return (message.text or "").partition(" ")[2].strip()


def _article_message(article: Article, query: str = "") -> str:
    """Render one article preview using Telegram HTML-safe formatting."""
    description = excerpt(
        article.text,
        query or article.title,
        limit=700,
    )
    return f"<b>{html.escape(article.title)}</b>\n{highlight_html(description, query)}"


def _article_keyboard(article: Article) -> InlineKeyboardMarkup:
    """Build the button linking to an article."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть статью", url=article.url)]
        ]
    )


def _search_keyboard(
    token: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup | None:
    """Build pagination controls for a search result page."""
    if total_pages <= 1:
        return None

    buttons: list[InlineKeyboardButton] = []

    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="← Назад",
                callback_data=f"s:{token}:{page - 1}",
            )
        )

    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="Вперёд →",
                callback_data=f"s:{token}:{page + 1}",
            )
        )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _render_search_page(
    results: list[Article],
    query: str,
    page: int,
) -> str:
    """Render one bounded full-text search result page."""
    total_pages = max(
        1,
        (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE,
    )
    page = max(1, min(page, total_pages))
    first = (page - 1) * RESULTS_PER_PAGE

    lines = [f"<b>Результаты поиска — {page}/{total_pages}</b>"]

    for article in results[first : first + RESULTS_PER_PAGE]:
        title = html.escape(article.title)
        url = html.escape(article.url, quote=True)
        snippet = highlight_html(
            excerpt(article.text, query),
            query,
        )
        lines.append(
            f'• <a href="{url}">{title}</a>\n{snippet}'
        )

    return "\n\n".join(lines)[:4096]


def _wiki_error_text(error: Exception) -> str:
    """Map known WikiClient exceptions to user-facing Telegram text."""
    if isinstance(error, UpstreamAccessError):
        return (
            "Источник запретил автоматический доступ. Для него нужен официальный API "
            "или разрешение владельца сайта."
        )
    if isinstance(error, UpstreamContentError):
        return (
            "Структура источника изменилась. "
            "Администратор уже получил диагностическую запись."
        )
    if isinstance(error, UpstreamNotFoundError):
        return "Статья больше не существует в источнике."
    if isinstance(error, UpstreamUnavailableError):
        return "Источник временно недоступен. Попробуйте немного позже."
    if isinstance(error, WikiError):
        return "Не удалось получить данные из источника. Попробуйте позже."
    return "Не удалось обработать команду. Попробуйте ещё раз позже."


async def _report_wiki_error(
    message: types.Message,
    error: Exception,
) -> None:
    """Log an error and send a safe user-facing message."""
    text = _wiki_error_text(error)

    if isinstance(error, UpstreamContentError):
        logger.error(
            "telegram_wiki_content_error error=%s",
            type(error).__name__,
        )
    elif isinstance(error, WikiError):
        logger.warning(
            "telegram_wiki_error error=%s",
            type(error).__name__,
        )
    else:
        logger.exception(
            "telegram_command_unexpected_error error=%s",
            type(error).__name__,
        )

    try:
        await message.answer(text)
    except Exception:
        logger.exception("telegram_error_message_failed")


def _is_valid_query(query: str) -> bool:
    return bool(query) and len(query) <= MAX_QUERY_LENGTH


def _send_search_result_count(results: list[Article]) -> int:
    return len(results)


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
        started_at = monotonic()

        try:
            article = await wiki.random_article()
            if article is None:
                await message.answer("Не нашёл подходящую публичную статью.")
                return

            await message.answer(
                _article_message(article),
                reply_markup=_article_keyboard(article),
            )
        except Exception as error:
            await _report_wiki_error(message, error)
        finally:
            logger.info(
                "telegram_command command=randompage duration_ms=%s",
                round((monotonic() - started_at) * 1000),
            )

    @router.message(Command("search"))
    async def search_title(message: types.Message) -> None:
        started_at = monotonic()
        query = _argument(message)

        if not query:
            await message.answer(
                "Укажите название: <code>/search название статьи</code>"
            )
            return

        if not _is_valid_query(query):
            await message.answer(
                f"Запрос должен быть от 1 до {MAX_QUERY_LENGTH} символов."
            )
            return

        try:
            article = await wiki.find_by_title(query)
            if article is None:
                await message.answer(
                    f"Статья «{html.escape(query)}» не найдена."
                )
                return

            await message.answer(
                _article_message(article, query),
                reply_markup=_article_keyboard(article),
            )
        except Exception as error:
            await _report_wiki_error(message, error)
        finally:
            logger.info(
                "telegram_command command=search query_length=%s duration_ms=%s",
                len(query),
                round((monotonic() - started_at) * 1000),
            )

    @router.message(Command("tags"))
    async def search_tags(message: types.Message) -> None:
        started_at = monotonic()
        tags = _argument(message).split()

        if not tags:
            await message.answer(
                "Укажите хотя бы один тег: <code>/tags тег1 тег2</code>"
            )
            return

        if len(tags) > MAX_TAGS:
            await message.answer(
                f"Можно указать не более {MAX_TAGS} тегов."
            )
            return

        if any(len(tag) > MAX_QUERY_LENGTH for tag in tags):
            await message.answer("Тег слишком длинный.")
            return

        articles: list[Article] = []

        try:
            articles = await wiki.find_by_tags(tags)
            if not articles:
                await message.answer("По этим тегам ничего не найдено.")
                return

            lines = [
                f"<b>Статьи с тегами: {html.escape(', '.join(tags))}</b>"
            ]
            for article in articles[:MAX_TAG_RESULTS]:
                lines.append(
                    f'• <a href="{html.escape(article.url, quote=True)}">'
                    f"{html.escape(article.title)}</a>"
                )

            await message.answer("\n".join(lines)[:4096])
        except Exception as error:
            await _report_wiki_error(message, error)
        finally:
            logger.info(
                "telegram_command command=tags tags_count=%s "
                "result_count=%s duration_ms=%s",
                len(tags),
                _send_search_result_count(articles),
                round((monotonic() - started_at) * 1000),
            )

    @router.message(Command("fullsearch"))
    async def search_content(message: types.Message) -> None:
        started_at = monotonic()
        query = _argument(message)
        results: list[Article] = []

        if not query:
            await message.answer(
                "Укажите текст: <code>/fullsearch поисковый запрос</code>"
            )
            return

        if not _is_valid_query(query):
            await message.answer(
                f"Запрос должен быть от 1 до {MAX_QUERY_LENGTH} символов."
            )
            return

        try:
            await message.bot.send_chat_action(message.chat.id, "typing")
            results = await wiki.search_content(query)

            if not results:
                await message.answer(
                    f"По запросу «{html.escape(query)}» ничего не найдено."
                )
                return

            token = searches.save(
                message.from_user.id,
                results,
                query,
            )
            total_pages = max(
                1,
                (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE,
            )

            await message.answer(
                _render_search_page(results, query, 1),
                reply_markup=_search_keyboard(token, 1, total_pages),
                disable_web_page_preview=True,
            )
        except Exception as error:
            await _report_wiki_error(message, error)
        finally:
            logger.info(
                "telegram_command command=fullsearch query_length=%s "
                "result_count=%s duration_ms=%s",
                len(query),
                _send_search_result_count(results),
                round((monotonic() - started_at) * 1000),
            )

    @router.callback_query(F.data.startswith("s:"))
    async def paginate(callback: types.CallbackQuery) -> None:
        data = callback.data or ""
        parts = data.split(":", 2)

        if len(parts) != 3 or parts[0] != "s":
            await callback.answer(
                "Некорректная кнопка.",
                show_alert=True,
            )
            return

        _, token, raw_page = parts

        try:
            page = int(raw_page)
        except ValueError:
            await callback.answer(
                "Некорректная страница.",
                show_alert=True,
            )
            return

        state = searches.get(token)
        if state is None:
            await callback.answer(
                "Результаты поиска устарели. Запустите поиск заново.",
                show_alert=True,
            )
            return

        if callback.from_user.id != state.owner_id:
            await callback.answer(
                "Эти результаты принадлежат другому пользователю.",
                show_alert=True,
            )
            return

        total_pages = max(
            1,
            (len(state.results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE,
        )
        page = max(1, min(page, total_pages))

        if callback.message is None:
            await callback.answer(
                "Сообщение с результатами недоступно.",
                show_alert=True,
            )
            return

        try:
            await callback.message.edit_text(
                _render_search_page(
                    state.results,
                    state.query,
                    page,
                ),
                reply_markup=_search_keyboard(
                    token,
                    page,
                    total_pages,
                ),
                disable_web_page_preview=True,
            )
            await callback.answer()
        except Exception:
            logger.exception("telegram_search_pagination_failed")
            await callback.answer(
                "Не удалось обновить результаты.",
                show_alert=True,
            )

    return router