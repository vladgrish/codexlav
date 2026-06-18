# Codexlav

Telegram-first cloud infra for running Codex remotely.

Codexlav packages a Telegram bot, GCE VM setup, GCS artifact delivery, and bootstrap scripts so you can run Codex from Telegram on your own cloud VM.

## What You Get

- Telegram bot control surface
- GCE VM runtime
- private group and topic workflow
- GCS artifact delivery for large files
- systemd user service
- caveman Codex skill install from `https://github.com/JuliusBrussee/caveman`
- reproducible bootstrap and release validation scripts

## Supported Environment

Target runtime:
- Debian 12 Bookworm on Google Compute Engine
- `bash`
- `git`
- `gh`
- `python3`
- `curl`
- `systemd --user`
- `gcloud` authenticated to your GCP project
- Codex CLI installed and available as `codex`

Verified baseline:
- VM image: Debian 12 Bookworm
- VM type: `e2-micro`
- zone: `us-central1-a`
- service account: VM compute service account
- OAuth scope: `cloud-platform`

## Setup Flow

Fast path:

1. Log in to Google Cloud Console.
2. Create a GCP project and enable billing.
3. Open Cloud Shell and run [`scripts/cloud_shell_bootstrap.sh`](scripts/cloud_shell_bootstrap.sh).
4. SSH into the VM.
5. Install Codex CLI.
6. Clone this repo.
7. Click through Telegram setup using [`docs/telegram-setup.md`](docs/telegram-setup.md): BotFather, create private group, enable topics, add bot.
8. Use Codex-assisted setup or run [`scripts/setup_vm.sh`](scripts/setup_vm.sh).
9. Test `/status` in Telegram.

## Cloud Shell VM Bootstrap

In Cloud Shell, run [`scripts/cloud_shell_bootstrap.sh`](scripts/cloud_shell_bootstrap.sh):

```bash
export GCP_PROJECT=your-gcp-project-id
export GCP_REGION=us-central1
export GCP_ZONE=us-central1-a
export VM_NAME=codexlav-vm
curl -fsS https://raw.githubusercontent.com/vladgrish/codexlav/main/scripts/cloud_shell_bootstrap.sh | bash
```

Alternative: copy [`scripts/cloud_shell_bootstrap.sh`](scripts/cloud_shell_bootstrap.sh) into Cloud Shell and run it there.

Then SSH into the VM:

```bash
gcloud compute ssh codexlav-vm --zone=us-central1-a
```

Install VM packages:

```bash
sudo apt-get update
sudo apt-get install -y git python3 gh curl
```

Install `gcloud` if missing. Install Codex CLI so `codex` is available on `PATH`.

Clone this repo:

```bash
git clone https://github.com/vladgrish/codexlav.git
cd codexlav
```

Authenticate GitHub CLI if this is a private repo. See [`docs/github-cli-git-access.md`](docs/github-cli-git-access.md).

## Telegram Setup

Use [`docs/telegram-setup.md`](docs/telegram-setup.md).

Minimum clicks:

1. Open BotFather.
2. Create bot.
3. Copy token.
4. Create private Telegram group.
5. Enable topics if you want per-topic Codex sessions.
6. Add bot to group.
7. Run [`scripts/setup_vm.sh`](scripts/setup_vm.sh), or use Codex-assisted setup below.

After setup, use [`docs/usage.md`](docs/usage.md) for DM, group, topic, restart, delete, image, handoff, and session commands.

## Codex-Assisted Setup

GCP project, billing, VM creation, and basic VM access happen outside this repo. After the VM exists and Codex CLI is installed, Codex can drive the rest from the docs.

From the VM, run Codex in the repo:

```bash
cd "$HOME"
git clone https://github.com/vladgrish/codexlav.git
cd codexlav
codex --yolo
```

Prompt:

```text
Set up Codexlav on this VM using the repo docs.

Read:
- README.md
- docs/config-reference.md
- docs/telegram-setup.md
- docs/gcs-artifacts.md
- docs/usage.md

Goal:
- create .env from env.example
- ask me only for missing values
- install caveman skill
- bootstrap GCP/GCS
- install and start user systemd service
- verify service status and Telegram /status path
- do not commit secrets
```

Use this path if you want Codex to inspect the VM state and adapt. Use the script path below if you want a direct shell setup.

## One-Shot VM Setup

Run [`scripts/setup_vm.sh`](scripts/setup_vm.sh):

```bash
scripts/setup_vm.sh
```

The script asks for:

- GCP project/region/zone
- Telegram bot token
- Telegram owner/user ID
- Telegram group chat ID
- Codex working directory
- GCS artifact bucket
- signing service account

It writes `.env`, configures GCS artifact storage, installs the systemd user service, and starts the bot.
It also installs or updates the caveman Codex skill from `https://github.com/JuliusBrussee/caveman`.

After first start, DM the bot with `/id` if you do not know your Telegram user ID. Re-run [`scripts/setup_vm.sh`](scripts/setup_vm.sh) with the returned ID.

## Configure

```bash
cp env.example .env
chmod 600 .env
```

Edit `.env` and set:

- `GCP_PROJECT`
- `GCP_REGION`
- `GCP_ZONE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS`
- `TELEGRAM_OWNER_USER_ID`
- `TELEGRAM_ALLOWED_CHAT_IDS`
- `CODEX_CWD`
- `CAVEMAN_SKILL_REPO`
- `GCS_ARTIFACT_BUCKET`
- `GCS_SIGNING_SERVICE_ACCOUNT`

Keep `.env` untracked. `.gitignore` already excludes it.

For every key and where to get it, see [`docs/config-reference.md`](docs/config-reference.md).

Before pushing changes, use [`docs/checkout-practice.md`](docs/checkout-practice.md) to keep `.env`, runtime state, and personal IDs out of git.

## Validate Local Host

Run [`scripts/check_local_requirements.sh`](scripts/check_local_requirements.sh):

```bash
scripts/check_local_requirements.sh
```

This checks required host commands before bootstrap.

## Install Caveman Skill

[`scripts/setup_vm.sh`](scripts/setup_vm.sh) runs this automatically. Manual install with [`scripts/install_caveman_skill.sh`](scripts/install_caveman_skill.sh):

```bash
scripts/install_caveman_skill.sh
```

Default source:

```text
https://github.com/JuliusBrussee/caveman
```

## Bootstrap GCP

Run [`scripts/bootstrap_gcp.sh`](scripts/bootstrap_gcp.sh):

```bash
scripts/bootstrap_gcp.sh
```

This sets active `gcloud` project/region/zone, enables required APIs, creates the GCS artifact bucket if missing, configures lifecycle cleanup, and grants signing/upload roles. Details: [`docs/gcs-artifacts.md`](docs/gcs-artifacts.md).

## Env Loading

The bot reads config from process environment with `os.environ`.

- systemd service uses `EnvironmentFile=/path/to/.env`
- [`scripts/run_bot.sh`](scripts/run_bot.sh) uses `set -a; . .env; set +a` so Python receives exported variables
- [`scripts/bootstrap_gcp.sh`](scripts/bootstrap_gcp.sh) sources `.env` for shell variables like `GCP_PROJECT`
- [`scripts/setup_vm.sh`](scripts/setup_vm.sh) writes `.env`, then calls the other scripts

You do not need to source `.env` manually for normal setup.

## Run Bot Manually

Run [`scripts/run_bot.sh`](scripts/run_bot.sh):

```bash
scripts/run_bot.sh
```

In Telegram, send `/id` to the bot in DM. Put the returned numeric user ID into `.env`, restart, then test with `/status`.

## Install User Service

Run [`scripts/install_systemd_user_service.sh`](scripts/install_systemd_user_service.sh):

```bash
scripts/install_systemd_user_service.sh
systemctl --user status telegram-codex-bot.service --no-pager -l
```

For a headless VM where the service must survive logout:

```bash
loginctl enable-linger "$USER"
```

Logs:

```bash
journalctl --user -u telegram-codex-bot.service -f
```

## Release Check

Before sharing or publishing:

Run [`scripts/validate_release.sh`](scripts/validate_release.sh):

```bash
scripts/validate_release.sh
```

This runs shell checks, Python syntax check, executable checks, and forbidden personal-data scans.

## Git Push

For GitHub HTTPS auth with GitHub CLI, see [`docs/github-cli-git-access.md`](docs/github-cli-git-access.md).

For a new empty remote:

```bash
git config --local user.name "Your Name"
git config --local user.email "you@example.com"
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/OWNER/codexlav.git
git push -u origin main
```

Use GitHub CLI credential helper for HTTPS. Do not put tokens in remote URLs.

## Do Not Commit

- `.env`
- Telegram bot token
- Telegram user IDs
- Telegram chat IDs
- GCP project IDs tied to a private account
- service account emails tied to a private project
- Codex session IDs
- local state files
