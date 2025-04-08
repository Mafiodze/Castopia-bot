from discord.ext import commands

class Dsc(commands.Cog):
    """Класс для инициализации кога.

    Args:
        commands (_type_): Наследует от класса commands.Cogs.
    """
    def __init__(self, bot) -> None:
        self.bot = bot

# константы для викидота
BASE_URL: str = "http://castopia-wiki.wikidot.com"
START_PAGE_URL: str = BASE_URL + "/system:all-pages"
TAGS_URL: str = BASE_URL + "/system:page-tags"
# константы для зеркала
BASE_URL_MIRROR: str = "https://castopia.obscurative.ru"
START_PAGE_URL_MIRROR: str = BASE_URL_MIRROR + "/system:all-pages"
TAGS_URL_MIRROR: str = BASE_URL_MIRROR + "/system:page-tags"
# настройки заголовков
HEADERS: dict = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/114.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}
# системные теги
SYSTEM_TAGS: set = {"компонент", "навигация", "поиск", "системный", "тест", "структура_сайта"}
# текст футера
FOOTER_TEXT = "Содержимое распространяется по лицензии CC BY-SA 3.0\n© [2025] [mafiodze]. Все права защищены."

async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(Dsc(bot))
