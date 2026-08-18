
#!/bin/bash

set -u

cd /app

echo "========================================"
echo "🚀 Starting Castopia Bot"
echo "========================================"
echo "Python: $(python --version)"
echo "Working directory: $(pwd)"
echo ""

# --------------------------------------------------
# Discord bot
# --------------------------------------------------

echo "🤖 Starting Discord bot..."

python -u /app/dsc/bot.py &
DISCORD_PID=$!

echo "✓ Discord bot started (PID: $DISCORD_PID)"
echo ""

# --------------------------------------------------
# Telegram bot
# --------------------------------------------------

echo "📱 Starting Telegram bot..."

python -u /app/tg/bot.py &
TELEGRAM_PID=$!

echo "✓ Telegram bot started (PID: $TELEGRAM_PID)"
echo ""

echo "========================================"
echo "✓ Discord + Telegram are running"
echo "========================================"
echo ""

# --------------------------------------------------
# Корректно завершаем дочерние процессы,
# когда Railway останавливает контейнер.
# --------------------------------------------------

cleanup() {
    echo ""
    echo "🛑 Stopping Castopia bots..."

    kill "$DISCORD_PID" 2>/dev/null || true
    kill "$TELEGRAM_PID" 2>/dev/null || true

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    echo "✓ Bots stopped"
}

trap cleanup SIGTERM SIGINT EXIT

# --------------------------------------------------
# Ждём оба процесса.
# Telegram и Discord полностью независимы.
# --------------------------------------------------

wait "$DISCORD_PID" &
WAIT_DISCORD=$!

wait "$TELEGRAM_PID" &
WAIT_TELEGRAM=$!

wait "$WAIT_DISCORD" || true
wait "$WAIT_TELEGRAM" || true

echo ""
echo "⚠️ One or both bots have stopped."
