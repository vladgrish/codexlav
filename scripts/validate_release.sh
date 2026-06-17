#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

required_files=(
  README.md
  PLAN.md
  SPEC.md
  .gitignore
  env.example
  scripts/check_local_requirements.sh
  scripts/cloud_shell_bootstrap.sh
  scripts/bootstrap_gcp.sh
  scripts/install_caveman_skill.sh
  scripts/setup_vm.sh
  scripts/run_bot.sh
  scripts/install_systemd_user_service.sh
  scripts/validate_release.sh
  docs/gcp-console-assistant-prompt.md
  docs/gcs-artifacts.md
  docs/github-cli-git-access.md
  docs/telegram-setup.md
  bot/bot.py
  bot/telegram-codex-bot.service
)

for path in "${required_files[@]}"; do
  [[ -f "$path" ]] || {
    echo "missing required file: $path" >&2
    exit 1
  }
done

for script in scripts/*.sh; do
  [[ -x "$script" ]] || {
    echo "script not executable: $script" >&2
    exit 1
  }
  bash -n "$script"
done

python3 -m py_compile bot/bot.py

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck scripts/*.sh
else
  echo "warning: shellcheck unavailable; skipped"
fi

for key in \
  GCP_PROJECT \
  GCP_REGION \
  GCP_ZONE \
  TELEGRAM_BOT_TOKEN \
  TELEGRAM_ALLOWED_USER_IDS \
  TELEGRAM_OWNER_USER_ID \
  TELEGRAM_ALLOWED_CHAT_IDS \
  CODEX_CWD \
  CAVEMAN_SKILL_REPO \
  GCS_ARTIFACT_BUCKET \
  GCS_ARTIFACT_RETENTION_DAYS \
  GCS_SIGNING_SERVICE_ACCOUNT; do
  grep -q "^${key}=" env.example || {
    echo "missing env.example key: $key" >&2
    exit 1
  }
done

for pattern in \
  '[0-9]{8,}:[A-Za-z0-9_-]{30,}' \
  'ctx7sk-[A-Za-z0-9-]+' \
  '/home/[A-Za-z0-9_.-]+' \
  '[0-9]{8,}-compute@developer\.gserviceaccount\.com' \
  'codex-[0-9]{6,}' \
  '019e[a-f0-9-]{20,}' \
  '[-]100[0-9]{8,}'; do
  if grep -RE --exclude-dir=.git -n -- "$pattern" .; then
    echo "forbidden private data pattern matched regex: $pattern" >&2
    exit 1
  fi
done

echo "release validation passed"
