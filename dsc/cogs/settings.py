import json
from discord.ext import commands

class Settings(commands.Cog):
    """Класс для пользовательских настроек бота.

    Args:
        commands (_type_): Наследует от класса commands.Cogs.
    """
    def __init__(self, bot) -> None:
        self.bot = bot

    def get_user_setting(user_id: str) -> str:
        """Получает настройки пользователя из JSON-файла.

        Args:
            user_id (str): ID пользователя.

        Returns:
            str: Настройки пользователя (викидот или зеркало).
        """
        try:
            with open("user_settings.json", "r", encoding="utf-8") as f:
                settings_data = json.load(f)
        except FileNotFoundError:
            settings_data = {}
        except json.JSONDecodeError:
            settings_data = {}
        return settings_data.get(user_id, "викидот").lower()
    
async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(Settings(bot))
