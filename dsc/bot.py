import os, sys, discord
from discord.ext import commands
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Ошибка: токен бота не найден. Проверьте .env файл!")

class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        if not os.path.exists(cogs_dir):
            raise FileNotFoundError(f"Папка 'cogs' не найдена по пути {cogs_dir}")
        for fn in os.listdir(cogs_dir):
            if fn.endswith(".py") and fn != "__init__.py":
                ext = f"cogs.{fn[:-3]}"
                try:
                    await self.load_extension(ext)
                    print(f"Загружен модуль: {ext}")
                except Exception as e:
                    print(f"Ошибка загрузки модуля {ext}: {e}")

bot = MyBot(command_prefix='.', intents=discord.Intents.all(), help_command=None)
if __name__ == "__main__":
    bot.run(TOKEN)
