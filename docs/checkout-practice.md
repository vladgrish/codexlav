# Checkout Practice

Use one checkout as source of truth:

```bash
cd ~/codexlav
git status --short --branch
```

The running service should execute this checkout's bot code. Do not maintain a second bot repo for live fixes.

## Secrets and Runtime State

Never commit runtime-only files:

- `.env`
- `.env.*`
- `state.json`
- `topic_state.json`
- `telegram_offset.json`
- `restart_notify.json`
- `imagegen_requests.jsonl`
- `generated/`
- `uploads/`
- `__pycache__/`

If a new config key is added to `.env`, it must also be added to:

- `env.example`
- `docs/config-reference.md`
- any setup script that writes `.env`

Use placeholder values in tracked files. Real tokens, chat IDs, user IDs, service account IDs, home paths, generated image IDs, and session IDs stay local.

## Before Commit

Run:

```bash
scripts/validate_release.sh
git status --short
git diff --check
```

Expected:

- no `.env` or runtime state files listed
- no private paths or IDs in tracked diffs
- `bot/bot.py` compiles
- every env key used by code exists in `env.example`
- every env key in `env.example` is documented in `docs/config-reference.md`
- if local `.env` exists, it has no keys missing from `env.example`

## Infra or Config Changes

For any new environment key, VM path, systemd setting, GCS behavior, Telegram command, or setup step:

1. Update code or script.
2. Update `env.example` if config changed.
3. Update `docs/config-reference.md` for every key.
4. Update `README.md` or `docs/usage.md` if user behavior changed.
5. Run `scripts/validate_release.sh`.

## Sync Rule

Commit public-safe source changes directly in `~/codexlav` and push `origin/main`.

If an emergency fix happens elsewhere, port only source changes into `~/codexlav`, run validation, then retire the other copy. Do not let live code and GitHub code diverge.
