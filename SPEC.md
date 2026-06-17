# Spec: Codexlav Template Release

## Goal

Release Codexlav as a shareable template for running Codex remotely through Telegram on a self-owned GCE VM.

## Product Definition

Codexlav is an operator-focused infra kit. A new user with a GCP account, Telegram account, and shell access must be able to clone the repo, configure `.env`, run scripts, and get a working Telegram-to-Codex bridge.

## Supported Environment

Required runtime:
- Debian 12 Bookworm on GCE
- `bash`
- `git`
- GitHub CLI available as `gh`
- `python3`
- `systemd --user`
- `gcloud`
- Codex CLI available as `codex`
- outbound network access to Telegram, OpenAI/Codex services, and Google Cloud APIs

Reference VM:
- GCE `e2-micro`
- `us-central1-a`
- Debian 12 Bookworm image
- default compute service account
- `cloud-platform` OAuth scope

## Required Configuration Keys

`env.example` must include these keys:
- `GCP_PROJECT`
- `GCP_REGION`
- `GCP_ZONE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS`
- `TELEGRAM_OWNER_USER_ID`
- `TELEGRAM_ALLOWED_CHAT_IDS`
- `CODEX_CWD`
- `CODEX_YOLO`
- `CODEX_STYLE_PREFIX`
- `CODEX_MODEL`
- `CODEX_MODEL_OPTIONS`
- `CODEX_REASONING_EFFORT`
- `OPENAI_API_KEY`
- `OPENAI_IMAGE_MODEL`
- `OPENAI_IMAGE_SIZE`
- `OPENAI_IMAGE_QUALITY`
- `TELEGRAM_ARTIFACT_MAX_BYTES`
- `GCS_ARTIFACT_BUCKET`
- `GCS_ARTIFACT_PREFIX`
- `GCS_ARTIFACT_RETENTION_DAYS`
- `GCS_SIGNED_URL_DURATION`
- `GCS_SIGNING_SERVICE_ACCOUNT`

## Forbidden Tracked Data

Tracked files must not contain:
- real Telegram bot tokens
- real Telegram user IDs
- real Telegram chat IDs
- personal email addresses
- personal home paths
- private GCP project IDs
- private service account emails
- Codex session IDs
- generated runtime state

## Required Files

- `README.md`
- `PLAN.md`
- `SPEC.md`
- `.gitignore`
- `env.example`
- `scripts/check_local_requirements.sh`
- `scripts/cloud_shell_bootstrap.sh`
- `scripts/bootstrap_gcp.sh`
- `scripts/setup_vm.sh`
- `scripts/run_bot.sh`
- `scripts/install_systemd_user_service.sh`
- `scripts/validate_release.sh`
- `docs/gcp-console-assistant-prompt.md`
- `docs/gcs-artifacts.md`
- `docs/github-cli-git-access.md`
- `docs/telegram-setup.md`
- `bot/bot.py`
- `bot/telegram-codex-bot.service`

## Functional Requirements

1. Fresh clone can pass `scripts/validate_release.sh`.
2. User can create `.env` from `env.example` and identify every required value from README/docs.
3. `scripts/check_local_requirements.sh` fails if required commands are missing.
4. `scripts/cloud_shell_bootstrap.sh` is runnable from GCP Cloud Shell after `GCP_PROJECT` is set and creates the VM if missing.
5. `scripts/bootstrap_gcp.sh` is rerunnable and creates/updates artifact bucket IAM, lifecycle cleanup, and signing prerequisites.
6. `scripts/setup_vm.sh` prompts for minimal operator input and runs local validation, GCP bootstrap, and service install.
7. `scripts/run_bot.sh` loads `.env` and starts `bot/bot.py`.
8. `scripts/install_systemd_user_service.sh` is rerunnable, writes a path-correct user service, reloads systemd, enables service, and starts/restarts it.
9. README includes zero-to-run commands for Cloud Shell bootstrap, VM setup, Telegram setup, GCS artifacts, logs, and git push.

## Acceptance Criteria

Release passes only when:
- `scripts/validate_release.sh` exits `0`.
- `bash -n scripts/*.sh` exits `0`.
- `python3 -m py_compile bot/bot.py` exits `0`.
- `scripts/check_local_requirements.sh` exits `0` on target VM.
- Fresh `.env` created from `env.example` can run `scripts/bootstrap_gcp.sh` in a test GCP project.
- GCS bucket has lifecycle deletion configured from `GCS_ARTIFACT_RETENTION_DAYS`.
- GCS signing docs cover `gcloud storage sign-url`, `roles/storage.objectAdmin`, and `roles/iam.serviceAccountTokenCreator`.
- `scripts/install_systemd_user_service.sh` creates an active `telegram-codex-bot.service`.
- Telegram `/status` returns from the bot after service start.
- forbidden-data scan finds no private identifiers.

## Non-Goals

- rewrite bot logic
- add new bot features
- manage secrets automatically
- support non-systemd deployment
- support non-GCP cloud bootstrap

## Release Gate

Maintainer must run:

```bash
scripts/validate_release.sh
git status --short
```

Expected:
- validation prints `release validation passed`
- no unreviewed generated files
- only intended tracked changes
