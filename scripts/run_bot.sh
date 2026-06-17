#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set -a
. "$ROOT_DIR/.env"
set +a

cd "$ROOT_DIR/bot"
python3 bot.py

