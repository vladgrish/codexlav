# Telegram Setup

## BotFather

1. Open Telegram.
2. Message `@BotFather`.
3. Run `/newbot`.
4. Choose display name and username.
5. Copy token into `TELEGRAM_BOT_TOKEN`.

## User ID

1. Start bot in private DM.
2. Send:

```text
/id
```

3. Copy numeric ID into:

```env
TELEGRAM_ALLOWED_USER_IDS=<your-id>
TELEGRAM_OWNER_USER_ID=<your-id>
```

`/id` works even before allowlist is configured.

## Group

1. Create private Telegram group.
2. Convert to supergroup if Telegram asks.
3. Enable topics if you want separate Codex sessions per topic.
4. Add bot to group.
5. Make bot admin if you want `/agent` topic creation and `/delete` topic deletion.
6. Get group chat ID:

```text
/id
```

If that does not show group ID, inspect logs:

```bash
journalctl --user -u telegram-codex-bot.service -f
```

Look for `chat_id=...`. Group IDs are negative, often starting with `-100`.

7. Set:

```env
TELEGRAM_ALLOWED_CHAT_IDS=<negative-group-id>
```

## Test

In DM:

```text
/status
```

In group general chat:

```text
/agent test
```

Open the created topic and send a normal prompt.

Do not commit real tokens or IDs.
