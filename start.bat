@echo off
REM Start both bots on Windows

echo 🚀 Starting Castopia Bot (Discord + Telegram)...

if not exist .env (
    echo ❌ .env not found. Copy from .env.example:
    echo   copy .env.example .env
    exit /b 1
)

echo Starting Discord bot...
start "Discord Bot" python dsc/bot.py

timeout /t 2 /nobreak

echo Starting Telegram bot...
start "Telegram Bot" python tg/bot.py

echo ✓ Both bots started (check the new windows)
echo.
echo To stop bots, close their windows
pause
