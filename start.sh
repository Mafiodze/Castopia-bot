#!/bin/bash

set -e

# Переходим в директорию, где находится start.sh
cd "$(dirname "$0")"

echo "========================================"
echo "🚀 Starting Castopia Bot"
echo "========================================"

# Проверяем .env
if [ ! -f ".env" ]; then
    echo "❌ .env not found!"
    echo "Create it from .env.example:"
    echo "cp .env.example .env"
    exit 1
fi

# Загружаем переменные из .env
set -a
source .env
set +a

echo "✓ .env loaded"
echo ""

# ----------------------------------------
# Запуск Discord
# ----------------------------------------

echo "🤖 Starting Discord bot..."
python dsc/bot.py &
DISCORD_PID=$!

echo "✓ Discord bot started (PID: $DISCORD_PID)"
echo ""

# ----------------------------------------
# Запуск Telegram
# ----------------------------------------

echo "📱 Starting Telegram bot..."
python tg/bot.py &
TELEGRAM_PID=$!

echo "✓ Telegram bot started (PID: $TELEGRAM_PID)"
echo ""

echo "========================================"
echo "✓ Both bots are running"
echo "========================================"
echo "Discord PID:  $DISCORD_PID"
echo "Telegram PID: $TELEGRAM_PID"
echo ""
echo "All bot output will appear below."
echo "========================================"
echo ""

# ----------------------------------------
# Остановка обоих ботов
# ----------------------------------------

cleanup() {
    echo ""
    echo "========================================"
    echo "🛑 Stopping bots..."
    echo "========================================"

    kill "$DISCORD_PID" 2>/dev/null || true
    kill "$TELEGRAM_PID" 2>/dev/null || true

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    echo "✓ Bots stopped"
}

trap cleanup EXIT INT TERM

# ----------------------------------------
# Ждём завершения процессов
# ----------------------------------------

wait "$DISCORD_PID" &
WAIT_DISCORD=$!

wait "$TELEGRAM_PID" &
WAIT_TELEGRAM=$!

# Если один из ботов завершился,
# ждём некоторое время, чтобы получить его код выхода
wait "$WAIT_DISCORD" 2>/dev/null || true
wait "$WAIT_TELEGRAM" 2>/dev/null || true

echo ""
echo "⚠️ One or both bots have stopped."