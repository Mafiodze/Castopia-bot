# Castopia Bot - Discord & Telegram Wiki Client

Быстрый поиск по публичной wiki через Discord и Telegram с поддержкой пагинации и полнотекстового поиска.

## Возможности

✅ **Discord Bot**
- Гибридные команды (prefix `.` + slash `/`)
- Autocomplete для `/search`
- Пагинация результатов (только для автора)
- Slash команды с deferred responses

✅ **Telegram Bot**
- 5 основных команд
- Inline пагинация
- Поддержка markdown разметки

✅ **Wiki Client**
- Кеширование (5-10 минут)
- Ограниченная конкурентность (макс 4 одновременных запроса)
- Полнотекстовый поиск с фильтрацией
- Диагностируемые ошибки

## Быстрый старт на Railway.app (Бесплатное облако)

### 1. Подготовка токенов

Получите:
- [Discord Bot Token](https://discord.com/developers/applications)
- [Telegram Bot Token](https://t.me/BotFather)

### 2. Развёртывание на Railway

```bash
# Клонировать репозиторий
git clone https://github.com/your-username/castopia-bot.git
cd castopia-bot

# Или создать новый Railway проект через UI
# https://railway.app/dashboard

# Через Railway CLI:
railway login
railway init
railway add
railway variables
```

### 3. Установка переменных окружения в Railway

В Railway Dashboard → Variables добавить:

```
DISCORD_BOT_TOKEN=ваш_токен_discord
TELEGRAM_BOT_TOKEN=ваш_токен_telegram
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=CastopiaBot/2.0
WIKI_MAX_CONCURRENCY=4
LOG_LEVEL=INFO
```

### 4. Запуск обоих ботов

Railway автоматически:
- Установит зависимости из `requirements.txt`
- Запустит оба бота согласно `Procfile`

## Локальная разработка

### Требования
- Python 3.12+
- pip

### Установка

```bash
# Клонировать
git clone https://github.com/your-username/castopia-bot.git
cd castopia-bot

# Виртуальное окружение
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/Mac)
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### Конфигурация

```bash
# Скопировать шаблон
cp .env.example .env

# Отредактировать .env с вашими токенами
# DISCORD_BOT_TOKEN=...
# TELEGRAM_BOT_TOKEN=...
```

### Запуск

```bash
# Discord бот
python dsc/bot.py

# Telegram бот (в другом терминале)
python tg/bot.py
```

## Структура проекта

```
castopia-bot/
├── dsc/
│   ├── __init__.py
│   ├── bot.py              # Discord bot entrypoint
│   └── requirements.txt    # Discord-specific deps
├── tg/
│   ├── __init__.py
│   ├── bot.py              # Telegram bot entrypoint
│   └── requirements.txt    # Telegram-specific deps
├── cogs/
│   ├── __init__.py
│   ├── constants.py        # Shared config
│   ├── dsc.py              # Discord commands
│   ├── page_parsing.py     # Wiki client (shared)
│   ├── settings.py         # Settings
│   ├── tg.py               # Telegram commands
│   └── txt_processing.py   # Text utils (shared)
├── tests/
│   ├── test_discord_ui.py
│   └── test_wiki_client.py
├── .env.example            # Config template
├── .gitignore
├── Procfile                # Railway process definitions
├── railway.json            # Railway configuration
├── requirements.txt        # Python dependencies
├── runtime.txt             # Python version
└── README.md              # This file
```

## Команды

### Discord

**Prefix версии** (начинаются с `.`):
```
.search <название>   - Найти статью по названию
.randompage          - Случайная публичная статья
.tags <тег> [тег…]   - Статьи с указанными тегами
.fullsearch <текст>  - Полнотекстовый поиск
.help                - Справка
```

**Slash версии** (начинаются с `/`):
```
/search              - С autocomplete по названиям
/randompage
/tags
/fullsearch
/help
```

### Telegram

```
/start или /help     - Справка
/search <название>   - Поиск по названию
/randompage          - Случайная статья
/tags <тег>          - Поиск по тегам
/fullsearch <текст>  - Полнотекстовый поиск
```

## Переменные окружения

| Переменная | Обязательна | Описание |
|-----------|-----------|---------|
| `DISCORD_BOT_TOKEN` | ✅ | Токен Discord бота |
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен Telegram бота |
| `WIKI_BASE_URL` | ❌ | URL wiki (по умолчанию https://castopia.site) |
| `WIKI_USER_AGENT` | ❌ | User-Agent для запросов |
| `WIKI_MAX_CONCURRENCY` | ❌ | Макс одновременных запросов (по умолчанию 4) |
| `DISCORD_GUILD_ID` | ❌ | ID гильдии для синхроизации slash команд |
| `LOG_LEVEL` | ❌ | INFO, DEBUG, WARNING (по умолчанию INFO) |

## Тестирование

```bash
# Запустить все тесты
python -m unittest discover tests/ -v

# Проверить синтаксис
python -m py_compile cogs/*.py dsc/bot.py tg/bot.py
```

**Результат**: 20/20 тестов passing ✅

## Логирование

Структурированные логи для мониторинга:
- `wiki_request` - HTTP запросы к wiki
- `wiki_fetch` - Кеширование страниц
- `wiki_links` - Загрузка списка статей
- `wiki_search` - Полнотекстовый поиск
- `discord_command` - Discord команды
- `telegram_command` - Telegram команды
- `discord_rate_*` - Rate limiting

Логи отправляются на:
- `stdout` (Railway логи автоматически собираются)
- Можно добавить интеграцию с сервисом мониторинга

## Обработка ошибок

### Wiki ошибки
- **403 Access Denied** - Источник запретил доступ (нужен API или разрешение)
- **429 Rate Limited** - Источник перегружен (бот ждёт и повторяет)
- **5xx Server Error** - Временная ошибка сервера (автоматический retry)
- **Structure Changed** - Разметка wiki изменилась (диагностическое сообщение)

### Rate Limiting
- Discord: 3 поиска за 20 сек, 1 полносеч за 30 сек
- Telegram: Не ограничивает (контролируется wiki кешем)

## Сотрудничество

Правила разработки:
1. Все команды должны быть в гибридной форме (prefix + slash для Discord)
2. Добавляйте unit-тесты для новых функций
3. Используйте структурированные логи
4. Ошибки wiki должны быть диагностируемыми
5. Русский язык для пользовательских сообщений

## Лицензия

CC BY-SA 3.0 - Содержимое wiki распространяется по этой лицензии

## Поддержка

- Issues: GitHub Issues
- Документация: README.md
- Контакт: Смотрите WIKI_USER_AGENT в .env.example

