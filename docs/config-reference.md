# Config Reference

This file explains every `.env` value and where to get it.

## GCP

`GCP_PROJECT`

Your Google Cloud project ID. Get it from Google Cloud Console project selector, or:

```bash
gcloud config get-value project
```

`GCP_REGION`

GCP region for the artifact bucket. Default:

```env
GCP_REGION=us-central1
```

`GCP_ZONE`

GCE VM zone. Default:

```env
GCP_ZONE=us-central1-a
```

`GCS_ARTIFACT_BUCKET`

Globally unique GCS bucket name for large files. Suggested:

```env
GCS_ARTIFACT_BUCKET=<project-id>-codexlav-artifacts
```

`GCS_ARTIFACT_PREFIX`

Object prefix inside the bucket:

```env
GCS_ARTIFACT_PREFIX=codex-artifacts
```

`GCS_ARTIFACT_RETENTION_DAYS`

How many days GCS keeps uploaded artifacts before lifecycle deletion:

```env
GCS_ARTIFACT_RETENTION_DAYS=7
```

`GCS_SIGNED_URL_DURATION`

How long signed artifact links work:

```env
GCS_SIGNED_URL_DURATION=15m
```

`GCS_SIGNING_SERVICE_ACCOUNT`

Service account used by `gcloud storage sign-url`. On a normal GCE VM, this is usually the active compute service account:

```bash
gcloud config get-value account
```

On the VM you can also inspect metadata:

```bash
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email
```

## Telegram

`TELEGRAM_BOT_TOKEN`

Create with BotFather:

1. Open Telegram.
2. Message `@BotFather`.
3. Run `/newbot`.
4. Copy the token BotFather returns.

`TELEGRAM_ALLOWED_USER_IDS`

Comma-separated Telegram user IDs allowed to use the bot. Get your ID by starting the bot and sending:

```text
/id
```

Before allowlist is configured, `/id` still works.

`TELEGRAM_OWNER_USER_ID`

User ID allowed to run owner-only controls such as `/bot`, `/restart`, `/delete`, `/model`, `/reason`, `/plan`, `/reload`, `/clear`, `/sessions`, and `/topicname`.

Usually same as `TELEGRAM_ALLOWED_USER_IDS`.

`TELEGRAM_ALLOWED_CHAT_IDS`

Comma-separated group chat IDs where the bot is allowed. Private DMs are allowed for allowlisted users.

Ways to get group ID:

1. Add bot to group.
2. Temporarily run bot and send `/id` in group.
3. If `/id` does not show group ID in your version, inspect logs:

```bash
journalctl --user -u telegram-codex-bot.service -f
```

Group IDs are usually negative and often start with `-100`.

## Codex

`CODEX_CWD`

Directory where Codex runs commands. Usually:

```env
CODEX_CWD=/home/<vm-user>
```

or a specific workspace/repo path.

`CODEX_YOLO`

Adds `--yolo` to Codex CLI when set to `1`:

```env
CODEX_YOLO=1
```

Use `0` if you want stricter Codex behavior.

`CODEX_STYLE_PREFIX`

Prompt prefix prepended to every Codex request. Default keeps Telegram replies short and formatted.

`CODEX_MODEL`

Default model:

```env
CODEX_MODEL=gpt-5.4-mini
```

`CODEX_MODEL_OPTIONS`

Model choices shown by `/model`.

`CODEX_REASONING_EFFORT`

Default reasoning choice:

```env
CODEX_REASONING_EFFORT=low
```

`CODEX_SESSION_ID`

Optional pinned Codex session UUID. Usually leave empty so topics map to their own sessions.

`CODEX_TIMEOUT_SECONDS`

Maximum seconds per Codex run.

## Skills

`CAVEMAN_SKILL_REPO`

Source repo for caveman skill:

```env
CAVEMAN_SKILL_REPO=https://github.com/JuliusBrussee/caveman.git
```

`CODEX_SKILLS_DIR`

Optional destination for Codex skills. Defaults to:

```text
~/.codex/skills
```

## OpenAI Image API

`OPENAI_API_KEY`

Optional. Needed only if you want `/image` to use the OpenAI Images API directly. If empty, bot falls back to Codex built-in `$imagegen` flow.

Create/get key from OpenAI dashboard, then set:

```env
OPENAI_API_KEY=...
```

`OPENAI_IMAGE_MODEL`

Default:

```env
OPENAI_IMAGE_MODEL=gpt-image-2
```

`OPENAI_IMAGE_SIZE`

Default:

```env
OPENAI_IMAGE_SIZE=1024x1024
```

`OPENAI_IMAGE_QUALITY`

Default:

```env
OPENAI_IMAGE_QUALITY=low
```

## Telegram Runtime Paths

Usually leave these unset:

- `TELEGRAM_HANDOFF_DIR`
- `TELEGRAM_POLL_TIMEOUT_SECONDS`
- `TELEGRAM_PROGRESS_UPDATE_SECONDS`
- `TELEGRAM_BOT_BASE_DIR`
- `TELEGRAM_IMAGE_DIR`
- `TELEGRAM_UPLOAD_DIR`
- `TELEGRAM_STATE_PATH`

