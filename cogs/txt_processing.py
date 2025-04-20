import re
from discord.ext import commands

class TextProcessing(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def trim_text(text: str, limit: int = 300) -> str:
        return text if len(text) <= limit else text[:limit-3] + "..."

    @staticmethod
    def highlight_sentence_markdown(sentence: str, query: str) -> str:
        query_words = query.split()
        for word in query_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            sentence = pattern.sub(lambda m: f"**{m.group(0)}**", sentence)
        return sentence.strip()
    
    @staticmethod
    def highlight_sentence_html(sentence: str, query: str) -> str:
        query_words = query.split()
        for word in query_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            sentence = pattern.sub(lambda m: f"<b>{m.group(0)}</b>", sentence)
        return sentence.strip()
    
    @staticmethod
    def extract_sentence_discord(text: str, query: str) -> str:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        query_lower = query.lower()
        for sentence in sentences:
            if query_lower in sentence.lower():
                text = TextProcessing.highlight_sentence_markdown(sentence, query)
                return TextProcessing.trim_text(text)
        query_words = query.split()
        for sentence in sentences:
            if any(qw.lower() in sentence.lower() for qw in query_words):
                text = TextProcessing.highlight_sentence_markdown(sentence, query)
                return TextProcessing.trim_text(text)
        return ""
    
    @staticmethod
    def extract_sentence_telegram(text: str, query: str) -> str:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        query_lower = query.lower()
        for sentence in sentences:
            if query_lower in sentence.lower():
                text = TextProcessing.highlight_sentence_html(sentence, query)
                return TextProcessing.trim_text(text)
        query_words = query.split()
        for sentence in sentences:
            if any(qw.lower() in sentence.lower() for qw in query_words):
                text = TextProcessing.highlight_sentence_html(sentence, query)
                return TextProcessing.trim_text(text)
        return ""
    
async def setup(bot) -> None:
    await bot.add_cog(TextProcessing(bot))
