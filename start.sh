#!/usr/bin/env bash
set -euo pipefail

# Load local .env only when it exists, which is useful for local runs.
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

service_name="${RAILWAY_SERVICE_NAME:-}"

if [[ -n "$service_name" ]]; then
  case "$service_name" in
    discord|discord-bot)
      echo "Starting Discord bot on Railway service: $service_name"
      exec python dsc/bot.py
      ;;
    telegram|telegram-bot)
      echo "Starting Telegram bot on Railway service: $service_name"
      exec python tg/bot.py
      ;;
    *)
      echo "Unknown Railway service name: $service_name; starting both bots as fallback"
      ;;
  esac
fi

if [[ -n "${DISCORD_BOT_TOKEN:-}" && -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "Starting both bots together (fallback mode)"
  python dsc/bot.py &
  discord_pid=$!
  python tg/bot.py &
  telegram_pid=$!
  trap 'kill $discord_pid $telegram_pid 2>/dev/null || true' EXIT
  wait "$discord_pid" "$telegram_pid"
  exit $?
fi

if [[ -n "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "Starting Discord bot"
  exec python dsc/bot.py
fi

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "Starting Telegram bot"
  exec python tg/bot.py
fi

echo "No bot tokens found. Ensure DISCORD_BOT_TOKEN and/or TELEGRAM_BOT_TOKEN are set in the environment."
exit 1
