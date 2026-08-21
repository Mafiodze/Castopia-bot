#!/bin/bash

set -euo pipefail

cd /app

DISCORD_PID=""
TELEGRAM_PID=""
SHUTTING_DOWN=0

log() {
    printf '[start] %s\n' "$*"
}

start_discord() {
    log "Starting Discord bot"
    python -u /app/dsc/bot.py &
    DISCORD_PID=$!
    log "Discord bot started (PID: $DISCORD_PID)"
}

start_telegram() {
    log "Starting Telegram bot"
    python -u /app/tg/bot.py &
    TELEGRAM_PID=$!
    log "Telegram bot started (PID: $TELEGRAM_PID)"
}

stop_process() {
    local pid="$1"
    local name="$2"

    if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
        return
    fi

    log "Stopping $name bot (PID: $pid)"
    kill "$pid" 2>/dev/null || true
}

stop_bots() {
    if (( SHUTTING_DOWN )); then
        return
    fi

    SHUTTING_DOWN=1
    log "Stopping Castopia bots"

    stop_process "$DISCORD_PID" "Discord"
    stop_process "$TELEGRAM_PID" "Telegram"

    wait "$DISCORD_PID" 2>/dev/null || true
    wait "$TELEGRAM_PID" 2>/dev/null || true

    log "Castopia bots stopped"
}

restart_discord() {
    if (( SHUTTING_DOWN )); then
        return
    fi

    log "Discord bot stopped. Restarting"
    wait "$DISCORD_PID" 2>/dev/null || true
    start_discord
}

restart_telegram() {
    if (( SHUTTING_DOWN )); then
        return
    fi

    log "Telegram bot stopped. Restarting"
    wait "$TELEGRAM_PID" 2>/dev/null || true
    start_telegram
}

trap stop_bots SIGTERM SIGINT

log "Starting Castopia Bot"
log "Python: $(python --version)"
log "Working directory: $(pwd)"

start_discord
start_telegram

log "Discord PID: $DISCORD_PID"
log "Telegram PID: $TELEGRAM_PID"

while (( ! SHUTTING_DOWN )); do
    if ! kill -0 "$DISCORD_PID" 2>/dev/null; then
        restart_discord
    fi

    if ! kill -0 "$TELEGRAM_PID" 2>/dev/null; then
        restart_telegram
    fi

    sleep 2 &
    SLEEP_PID=$!

    wait "$SLEEP_PID" 2>/dev/null || true

    if (( SHUTTING_DOWN )); then
        break
    fi
done

stop_bots