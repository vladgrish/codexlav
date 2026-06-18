# Usage

## Chat Modes

Private DM:

- Good for owner controls, quick prompts, `/restart`, `/status`, `/id`.
- Any allowlisted user can use the bot in DM.

Group general chat:

- Bot does not run Codex work directly in the general thread.
- Ask it to create a topic with `/agent` or a message like `create topic for deploy work`.
- General chat is for session controls and creating topics.

Group topic:

- Main work mode.
- Each topic gets its own Codex session.
- Send normal text to run Codex in that topic.
- Send images or files to analyze them.

## First Test

In DM:

```text
/id
/status
```

In group:

```text
/agent
```

Then open the created topic and send:

```text
date
```

## Commands

`/start` or `/help`

Show help.

`/id`

Show your Telegram user ID. Works before allowlist is configured.

`/status`

Show current config: Codex cwd, model, reasoning, yolo mode, queue depth, topic session, and rate-limit status.

`/agent`

In group general chat, creates a new topic/session.

`/agent <name>`

Creates a topic with a name based on the text.

`/model`

Owner-only. Shows model picker buttons.

`/reason` or `/reasoning`

Owner-only. Shows reasoning-effort picker buttons.

`/plan`

Owner-only. Sets current topic to plan mode. Next user request asks Codex for a plan instead of executing.

`/reload`

Owner-only. Clears current topic's Codex session. Next prompt starts fresh.

`/clear`

Owner-only. Clears current topic session and returns topic to chat mode.

`/delete`

Owner-only. Works only inside a group topic. Deletes the Telegram topic, clears stored state, and tries to archive the mapped Codex session.

`/restart`

Owner-only. Works in owner private DM. Shows restart button and restarts the user systemd service when clicked.

`/recap`

Creates a one-sentence recap of the current topic session.

`/sessions`

Shows known topic/session mappings and recaps.

`/topicname <name>`

Owner-only. Sets display name for current topic in session listings.

`/handoff`

Writes a Markdown handoff document for the current topic session and sends it back as a file.

`/image <prompt>`

Generates an image.

- If `OPENAI_API_KEY` is set: uses OpenAI Images API.
- If not set: uses Codex built-in `$imagegen` and returns the generated PNG.

`/lastimage`

Sends newest generated image found under Codex generated image directory.

`/images`

Shows recent generated images.

`/bot <task>`

Owner-only. Runs a Codex task against the bot/local ecosystem. Use for maintenance work.

Bot maintenance tasks must work in the `codexlav` checkout on a feature branch. Before finishing, Codex should run:

```bash
scripts/validate_release.sh
```

If validation passes, Codex should commit on the feature branch, merge back to `main`, and leave `main` checked out. It must not commit `.env`, runtime state, uploads, generated files, tokens, chat IDs, user IDs, local absolute home paths, or other private machine data.

## Files And Images

Send photo with caption:

```text
what is wrong in this screenshot?
```

Send text file:

```text
summarize this log and list likely root causes
```

Large artifacts:

- Files smaller than `TELEGRAM_ARTIFACT_MAX_BYTES` are sent directly to Telegram.
- Larger files upload to GCS.
- Bot returns a signed URL valid for `GCS_SIGNED_URL_DURATION`.

## Restart And Logs

Restart from VM:

```bash
systemctl --user restart telegram-codex-bot.service
```

Logs:

```bash
journalctl --user -u telegram-codex-bot.service -f
```

Status:

```bash
systemctl --user status telegram-codex-bot.service --no-pager -l
```

## Common Flow

1. DM bot `/status`.
2. In group general chat, run `/agent deploy fix`.
3. Open new topic.
4. Send request, image, or file.
5. Use `/recap` before switching context.
6. Use `/handoff` when work should continue later.
7. Use `/delete` when topic is done.
