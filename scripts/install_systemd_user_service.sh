#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.config/systemd/user"
SERVICE_PATH="$HOME/.config/systemd/user/telegram-codex-bot.service"

cat >"$SERVICE_PATH" <<SERVICE
[Unit]
Description=Telegram bridge for Codex CLI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT_DIR/bot
EnvironmentFile=$ROOT_DIR/.env
ExecStart=/usr/bin/python3 $ROOT_DIR/bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable telegram-codex-bot.service
systemctl --user restart telegram-codex-bot.service
