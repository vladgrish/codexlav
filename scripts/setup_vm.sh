#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

prompt_default() {
  local name="$1"
  local default="$2"
  local value
  read -r -p "$name [$default]: " value
  printf '%s' "${value:-$default}"
}

prompt_secret() {
  local name="$1"
  local value
  read -r -s -p "$name: " value
  printf '\n' >&2
  printf '%s' "$value"
}

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT_DIR/env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

GCP_PROJECT="$(prompt_default GCP_PROJECT "your-gcp-project-id")"
GCP_REGION="$(prompt_default GCP_REGION "us-central1")"
GCP_ZONE="$(prompt_default GCP_ZONE "us-central1-a")"
TELEGRAM_BOT_TOKEN="$(prompt_secret TELEGRAM_BOT_TOKEN)"
TELEGRAM_ALLOWED_USER_IDS="$(prompt_default TELEGRAM_ALLOWED_USER_IDS "replace_me_user_id")"
TELEGRAM_ALLOWED_CHAT_IDS="$(prompt_default TELEGRAM_ALLOWED_CHAT_IDS "replace_me_group_chat_id")"
CODEX_CWD="$(prompt_default CODEX_CWD "$HOME")"
GCS_ARTIFACT_BUCKET="$(prompt_default GCS_ARTIFACT_BUCKET "${GCP_PROJECT}-codexlav-artifacts")"
GCS_SIGNING_SERVICE_ACCOUNT="$(prompt_default GCS_SIGNING_SERVICE_ACCOUNT "$(gcloud config get-value account 2>/dev/null || true)")"
GCS_ARTIFACT_RETENTION_DAYS="$(prompt_default GCS_ARTIFACT_RETENTION_DAYS "7")"

cat >"$ENV_FILE" <<ENV
GCP_PROJECT=$GCP_PROJECT
GCP_REGION=$GCP_REGION
GCP_ZONE=$GCP_ZONE

TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USER_IDS=$TELEGRAM_ALLOWED_USER_IDS
TELEGRAM_OWNER_USER_ID=$TELEGRAM_ALLOWED_USER_IDS
TELEGRAM_ALLOWED_CHAT_IDS=$TELEGRAM_ALLOWED_CHAT_IDS

CODEX_CWD=$CODEX_CWD
CODEX_YOLO=1
CODEX_STYLE_PREFIX="Answer in caveman full by default. Preserve user's dominant language. Keep replies terse, factual, and direct. For mission-critical cmd or code work, report in formatted sections with a label line like COMMAND or RESULT, then the command or output body on the next lines."
CODEX_MODEL=gpt-5.4-mini
CODEX_MODEL_OPTIONS=default,gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3
CODEX_REASONING_EFFORT=low
CAVEMAN_SKILL_REPO=https://github.com/JuliusBrussee/caveman.git

OPENAI_API_KEY=
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=low

TELEGRAM_ARTIFACT_MAX_BYTES=10000000
GCS_ARTIFACT_BUCKET=$GCS_ARTIFACT_BUCKET
GCS_ARTIFACT_PREFIX=codex-artifacts
GCS_ARTIFACT_RETENTION_DAYS=$GCS_ARTIFACT_RETENTION_DAYS
GCS_SIGNED_URL_DURATION=15m
GCS_SIGNING_SERVICE_ACCOUNT=$GCS_SIGNING_SERVICE_ACCOUNT
ENV

chmod 600 "$ENV_FILE"
"$ROOT_DIR/scripts/check_local_requirements.sh"
"$ROOT_DIR/scripts/install_caveman_skill.sh"
"$ROOT_DIR/scripts/bootstrap_gcp.sh"
"$ROOT_DIR/scripts/install_systemd_user_service.sh"

echo "setup done"
echo "test in Telegram: /status"
