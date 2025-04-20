import os
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

PARENT_DIR = os.path.dirname(os.path.dirname(__file__)) 
sys.path.insert(0, PARENT_DIR)
COGS_DIR = os.path.join(PARENT_DIR, "cogs")
load_dotenv(os.path.join(PARENT_DIR, ".env"))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

class MyBot(commands.Bot):
    async def setup_hook(self):
        if not os.path.exists(COGS_DIR):
            raise FileNotFoundError(f"Папка 'cogs' не найдена по пути: {COGS_DIR}")

        for file_name in os.listdir(COGS_DIR):
            if file_name.endswith(".py") and file_name != "__init__.py" and file_name != "tg.py":
                extension_name = f"cogs.{file_name[:-3]}"
                try:
                    await self.load_extension(extension_name)
                    print(f"Загружен модуль: {extension_name}")
                except Exception as e:
                    print(f"Ошибка загрузки модуля {extension_name}: {e}")

bot = MyBot(command_prefix='.', intents=discord.Intents.all(), help_command=None)

if __name__ == "__main__":
    bot.run(TOKEN)
