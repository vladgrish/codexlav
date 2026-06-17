#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

: "${CAVEMAN_SKILL_REPO:=https://github.com/JuliusBrussee/caveman.git}"
: "${CODEX_SKILLS_DIR:=$HOME/.codex/skills}"

TARGET_DIR="$CODEX_SKILLS_DIR/caveman"
mkdir -p "$CODEX_SKILLS_DIR"

if [[ -d "$TARGET_DIR/.git" ]]; then
  git -C "$TARGET_DIR" pull --ff-only
elif [[ -e "$TARGET_DIR" ]]; then
  echo "caveman skill path exists but is not a git repo: $TARGET_DIR" >&2
  echo "move it aside or set CODEX_SKILLS_DIR to another directory" >&2
  exit 1
else
  git clone "$CAVEMAN_SKILL_REPO" "$TARGET_DIR"
fi

test -f "$TARGET_DIR/SKILL.md" || {
  echo "missing SKILL.md in $TARGET_DIR" >&2
  exit 1
}

echo "caveman skill installed: $TARGET_DIR"
