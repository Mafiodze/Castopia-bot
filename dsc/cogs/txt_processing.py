import re
from discord.ext import commands

class TextProcessing(commands.Cog):
    """Класс для обработки текста.

    Args:
        commands (_type_): Наследует от класса commands.Cogs.
    """
    def __init__(self, bot) -> None:
        self.bot = bot

    def trim_text(self, text: str, limit: int = 300) -> str:
        """Обрезает текст до указанного количества символов.

        Args:
            text (str): Текст для обрезки.
            limit (int, optional): Лимит текста. Defaults to 300.

        Returns:
            str: Обрезанный текст.
        """
        return text if len(text) <= limit else text[:limit-3] + "..."

    @staticmethod
    def highlight_sentence(sentence: str, query: str) -> str:
        """Выделяет ключевые слова в предложении.

        Args:
            sentence (str): Предложение.
            query (str): Поисковый запрос.

        Returns:
            str: Предложение с выделенными ключевыми словами.
        """
        query_words = query.split()
        for word in query_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            sentence = pattern.sub(lambda m: f"**{m.group(0)}**", sentence)
        return sentence.strip()
    
    @staticmethod
    def extract_sentence(text: str, query: str, window: int = 2) -> str:
        """Извлекает предложение с ключевыми словами.

        Args:
            text (str): Текст статьи.
            query (str): Поисковый запрос.
            window (int, optional): Количество слов после первого/последнего ключевого. 2 по умолчанию.

        Returns:
            str: Предложение с ключевыми словами.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        query_lower = query.lower()
        for sentence in sentences:
            if query_lower in sentence.lower():
                return TextProcessing.highlight_sentence(sentence, query)
        query_words = query.split()
        for sentence in sentences:
            if any(qw.lower() in sentence.lower() for qw in query_words):
                return TextProcessing.highlight_sentence(sentence, query)
        return ""
    
async def setup(bot) -> None:
    """Глобальная функция для инициализации кога.

    Args:
        bot (_type_): Экземпляр бота.
    """
    await bot.add_cog(TextProcessing(bot))
