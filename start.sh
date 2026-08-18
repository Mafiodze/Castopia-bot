#!/bin/bash

set -e

cd "$(dirname "$0")"

echo "🚀 Starting Castopia Bot (Discord + Telegram)..."

if [ ! -f .env ]; then
    echo "❌ .env not found"
    exit 1
fi

set -a
source .env
set +a

echo "Starting Discord bot..."
python dsc/bot.py > discord.log 2>&1 &
DISCORD_PID=$!

echo "Starting Telegram bot..."
python tg/bot.py > telegram.log 2>&1 &
TELEGRAM_PID=$!

echo "✓ Discord PID: $DISCORD_PID"
echo "✓ Telegram PID: $TELEGRAM_PID"

trap 'kill $DISCORD_PID $TELEGRAM_PID 2>/dev/null || true' EXIT

wait