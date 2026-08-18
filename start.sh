#!/bin/bash

set -u

cd /app

echo "========================================"
echo "🚀 Starting Castopia Bot"
echo "========================================"

# --------------------------------------------------
# Загружаем .env, если он существует
# --------------------------------------------------

if [ -f "/app/.env" ]; then
    echo "✓ Loading .env"

    set -a
    # shellcheck disable=SC1091
    source /app/.env
    set +a
else
    echo "✓ Using environment variables from container"
fi

echo ""

# --------------------------------------------------
# Проверяем Python
# --------------------------------------------------

echo "Python: $(python --version)"
echo "Working directory: $(pwd)"
echo ""

# --------------------------------------------------
# Запуск Discord
# --------------------------------------------------

echo "========================================"
echo "🤖 Starting Discord bot..."
echo "========================================"

python -u /app/dsc/bot.py &
DISCORD_PID=$!

echo "✓ Discord process started: PID $DISCORD_PID"
echo ""

# --------------------------------------------------
# Запуск Telegram
# --------------------------------------------------

echo "========================================"
echo "📱 Starting Telegram bot..."
echo "========================================"

python -u /app/tg/bot.py &
TELEGRAM_PID=$!

echo "✓ Telegram process started: PID $TELEGRAM_PID"
echo ""

# --------------------------------------------------
# Показать состояние
# --------------------------------------------------

echo "========================================"
echo "✓ Castopia bots started"
echo "========================================"
echo "Discord PID : $DISCORD_PID"
echo "Telegram PID: $TELEGRAM_PID"
echo "========================================"
echo ""

# --------------------------------------------------
# Корректное завершение контейнера
# --------------------------------------------------

cleanup() {
    echo ""
    echo "========================================"
    echo "🛑 Stopping Castopia bots..."
    echo "========================================"

    if kill -0 "$DISCORD_PID" 2>/dev/null; then
        kill "$DISCORD_PID" 2>/dev/null || true
    fi

    if kill -0 "$TELEGRAM_PID" 2>/dev/null; then
        kill "$TELEGRAM_PID" 2>/dev/null || true
    fi

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    echo "✓ Bots stopped"
}

trap cleanup SIGINT SIGTERM EXIT

# --------------------------------------------------
# Следим за обоими процессами
# --------------------------------------------------

while true; do
    if ! kill -0 "$DISCORD_PID" 2>/dev/null; then
        echo "❌ Discord bot stopped."
        echo "🛑 Stopping container..."
        exit 1
    fi

    if ! kill -0 "$TELEGRAM_PID" 2>/dev/null; then
        echo "❌ Telegram bot stopped."
        echo "🛑 Stopping container..."
        exit 1
    fi

    sleep 5
done