#!/bin/bash

set -u

cd /app

echo "========================================"
echo "🚀 Starting Castopia Bot"
echo "========================================"
echo "Python: $(python --version)"
echo "Working directory: $(pwd)"
echo ""

DISCORD_PID=""
TELEGRAM_PID=""

# --------------------------------------------------
# Start Discord
# --------------------------------------------------

start_discord() {
    echo "🤖 Starting Discord bot..."

    python -u /app/dsc/bot.py &
    DISCORD_PID=$!

    echo "✓ Discord started (PID: $DISCORD_PID)"
}

# --------------------------------------------------
# Start Telegram
# --------------------------------------------------

start_telegram() {
    echo "📱 Starting Telegram bot..."

    python -u /app/tg/bot.py &
    TELEGRAM_PID=$!

    echo "✓ Telegram started (PID: $TELEGRAM_PID)"
}

# --------------------------------------------------
# Stop bots
# --------------------------------------------------

stop_bots() {
    echo ""
    echo "🛑 Stopping Castopia bots..."

    if [ -n "$DISCORD_PID" ]; then
        kill "$DISCORD_PID" 2>/dev/null || true
    fi

    if [ -n "$TELEGRAM_PID" ]; then
        kill "$TELEGRAM_PID" 2>/dev/null || true
    fi

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    echo "✓ Bots stopped"
}

trap stop_bots SIGTERM SIGINT EXIT

# --------------------------------------------------
# Start both bots
# --------------------------------------------------

start_discord
start_telegram

echo ""
echo "========================================"
echo "✓ BOTH BOTS ARE RUNNING"
echo "========================================"
echo "Discord PID : $DISCORD_PID"
echo "Telegram PID: $TELEGRAM_PID"
echo "========================================"
echo ""

# --------------------------------------------------
# Monitor both processes
# --------------------------------------------------

while true; do
    sleep 5

    # Discord stopped
    if ! kill -0 "$DISCORD_PID" 2>/dev/null; then
        echo "⚠️ Discord bot stopped. Restarting..."
        wait "$DISCORD_PID" 2>/dev/null || true
        start_discord
    fi

    # Telegram stopped
    if ! kill -0 "$TELEGRAM_PID" 2>/dev/null; then
        echo "⚠️ Telegram bot stopped. Restarting..."
        wait "$TELEGRAM_PID" 2>/dev/null || true
        start_telegram
    fi
done