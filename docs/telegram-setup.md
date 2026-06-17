# Telegram Setup

1. Create a bot with BotFather.
2. Put the token into `.env`.
3. Start the bot once in a private DM and run `/id`.
4. Put that numeric user id into `TELEGRAM_ALLOWED_USER_IDS` and `TELEGRAM_OWNER_USER_ID`.
5. Create a private supergroup and enable topics if you want per-topic Codex sessions.
6. Add the bot to the group.
7. Send `/id` in the group, or inspect bot logs, to get the negative group chat id.
8. Put the group chat id into `TELEGRAM_ALLOWED_CHAT_IDS`.
9. Keep the group private and keep allowlists enabled.
10. Test `/status` after service start.

Do not commit real tokens or ids.
