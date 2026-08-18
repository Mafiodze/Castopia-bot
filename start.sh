#!/bin/bash

set -u

cd /app

echo "========================================"
echo "🚀 Starting Castopia Bot"
echo "========================================"

# Загружаем .env, если он есть.
# На облачной платформе переменные окружения тоже будут работать.
if [ -f "/app/.env" ]; then
    set -a
    source /app/.env
    set +a
    echo "✓ .env loaded"
else
    echo "✓ Using container environment variables"
fi

echo ""

# Останавливаем оба процесса при завершении контейнера.
cleanup() {
    echo ""
    echo "🛑 Stopping bots..."

    kill "$DISCORD_PID" 2>/dev/null || true
    kill "$TELEGRAM_PID" 2>/dev/null || true

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    echo "✓ Bots stopped"
}

trap cleanup SIGTERM SIGINT EXIT

# --------------------------------------------------
# Discord
# --------------------------------------------------

echo "🤖 Starting Discord bot..."

python -u /app/dsc/bot.py &
DISCORD_PID=$!

echo "✓ Discord started, PID=$DISCORD_PID"

# --------------------------------------------------
# Telegram
# --------------------------------------------------

echo "📱 Starting Telegram bot..."

python -u /app/tg/bot.py &
TELEGRAM_PID=$!

echo "✓ Telegram started, PID=$TELEGRAM_PID"

echo ""
echo "========================================"
echo "✓ Both bots are running"
echo "========================================"
echo ""

# --------------------------------------------------
# Оба процесса работают независимо.
#
# Если Telegram временно получает Conflict во время
# redeploy, Discord от этого НЕ останавливается.
# --------------------------------------------------

while true; do
    sleep 5

    # Проверяем только наличие процессов.
    # Не завершаем второй бот, если первый закончился.
    if ! kill -0 "$DISCORD_PID" 2>/dev/null; then
        echo "⚠️ Discord process stopped."
        DISCORD_PID=""
    fi

    if ! kill -0 "$TELEGRAM_PID" 2>/dev/null; then
        echo "⚠️ Telegram process stopped."
        TELEGRAM_PID=""
    fi

    # Если оба процесса завершились, завершаем контейнер.
    if [ -z "$DISCORD_PID" ] && [ -z "$TELEGRAM_PID" ]; then
        echo "❌ Both bots stopped."
        exit 1
    fi
done