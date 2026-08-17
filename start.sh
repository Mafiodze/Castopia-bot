#!/bin/bash
# Start both bots concurrently

set -e

echo "🚀 Starting Castopia Bot (Discord + Telegram)..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env not found. Copy from .env.example:"
    echo "  cp .env.example .env"
    exit 1
fi

# Function to run bot
run_bot() {
    local bot_type=$1
    local script=$2
    echo "Starting $bot_type bot..."
    python "$script"
}

# Export environment for both processes
export $(grep -v '^#' .env | xargs)

# Run both bots
run_bot "Discord" "dsc/bot.py" &
DISCORD_PID=$!

run_bot "Telegram" "tg/bot.py" &
TELEGRAM_PID=$!

# Cleanup on exit
trap "kill $DISCORD_PID $TELEGRAM_PID 2>/dev/null; echo '✓ Bots stopped'" EXIT

echo "✓ Both bots running (PIDs: $DISCORD_PID, $TELEGRAM_PID)"
echo "Press Ctrl+C to stop"

# Wait for all background processes
wait
