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
  docs/checkout-practice.md
  docs/gcp-console-assistant-prompt.md
  docs/config-reference.md
  docs/gcs-artifacts.md
  docs/github-cli-git-access.md
  docs/telegram-setup.md
  docs/usage.md
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

python3 - <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(".")

def env_keys(path: pathlib.Path, include_commented: bool = False) -> set[str]:
    keys: set[str] = set()
    pattern = re.compile(r"^\s*(?:#\s*)?([A-Z][A-Z0-9_]*)=" if include_commented else r"^\s*([A-Z][A-Z0-9_]*)=")
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if match:
            keys.add(match.group(1))
    return keys

example_keys = env_keys(root / "env.example", include_commented=True)
config_doc = (root / "docs/config-reference.md").read_text()
bot_text = (root / "bot/bot.py").read_text()
code_keys = set(re.findall(r'os\.environ\.get\("([A-Z][A-Z0-9_]*)"', bot_text))

missing_from_example = sorted(code_keys - example_keys)
if missing_from_example:
    print("env keys used in bot/bot.py but missing from env.example:", file=sys.stderr)
    for key in missing_from_example:
        print(f"  {key}", file=sys.stderr)
    sys.exit(1)

missing_from_docs = sorted(key for key in example_keys if f"`{key}`" not in config_doc)
if missing_from_docs:
    print("env.example keys missing from docs/config-reference.md:", file=sys.stderr)
    for key in missing_from_docs:
        print(f"  {key}", file=sys.stderr)
    sys.exit(1)

env_path = root / ".env"
if env_path.exists():
    env_only = sorted(env_keys(env_path) - example_keys)
    if env_only:
        print(".env has keys missing from env.example:", file=sys.stderr)
        for key in env_only:
            print(f"  {key}", file=sys.stderr)
        sys.exit(1)
PY

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
