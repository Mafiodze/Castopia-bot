from discord.ext import commands

class Constants(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

BASE_URL = "http://castopia-wiki.wikidot.com"
START_PAGE_URL = f"{BASE_URL}/system:all-pages"
TAGS_URL = f"{BASE_URL}/system:page-tags"

BASE_URL_MIRROR = "https://castopia.obscurative.ru"
START_PAGE_URL_MIRROR = f"{BASE_URL_MIRROR}/system:all-pages"
TAGS_URL_MIRROR = f"{BASE_URL_MIRROR}/system:page-tags"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/114.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}
SYSTEM_TAGS = {"компонент", "навигация", "поиск", "системный", "тест", "структура_сайта"}

FOOTER_TEXT = ("Содержимое распространяется по лицензии CC BY-SA 3.0\n"
               "© [2025] [mafiodze]. Все права защищены.")

async def setup(bot) -> None:
    await bot.add_cog(Constants(bot))
