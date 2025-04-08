import json
from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def get_user_setting(user_id: str) -> str:
        try:
            with open("user_settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        return data.get(user_id, "викидот").lower()

async def setup(bot) -> None:
    await bot.add_cog(Settings(bot))