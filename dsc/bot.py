import os
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not DISCORD_BOT_TOKEN:
    raise ValueError("Ошибка: токен бота не найден. Проверьте .env файл!")

class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")

        if not os.path.exists(cogs_path):
            raise FileNotFoundError(f"Ошибка: папка 'cogs' не найдена по пути {cogs_path}")
        
        for filename in os.listdir(cogs_path):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"cogs.{filename[:-3]}" 
                try:
                    await self.load_extension(cog_name)
                    print(f"Загружен модуль: {cog_name}")
                except Exception as e:
                    print(f"Ошибка загрузки модуля {cog_name}: {e}")

bot = MyBot(command_prefix='.', intents=discord.Intents.all(), help_command=None)

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
