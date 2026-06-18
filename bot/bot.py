#!/usr/bin/env python3
import base64
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import selectors
import shlex
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2").strip()
OPENAI_IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024").strip()
OPENAI_IMAGE_QUALITY = os.environ.get("OPENAI_IMAGE_QUALITY", "low").strip()
ALLOWED_IDS = {
    item.strip()
    for item in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if item.strip()
}
ALLOWED_CHAT_IDS = {
    item.strip()
    for item in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if item.strip()
}
OWNER_USER_IDS = {
    item.strip()
    for item in os.environ.get("TELEGRAM_OWNER_USER_ID", "").split(",")
    if item.strip()
}
CODEX_CWD = os.environ.get("CODEX_CWD", os.getcwd())
CODEX_SESSION_ID = os.environ.get("CODEX_SESSION_ID", "").strip()
CODEX_MODEL_DEFAULT = os.environ.get("CODEX_MODEL", "gpt-5.4-mini").strip()
CODEX_REASONING_DEFAULT = os.environ.get("CODEX_REASONING_EFFORT", "low").strip()
CODEX_MODEL_OPTIONS = [
    item.strip()
    for item in os.environ.get("CODEX_MODEL_OPTIONS", "default,gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3").split(",")
    if item.strip()
]
REASONING_OPTIONS = ["low", "medium", "high", "xhigh"]
REASONING_DESCRIPTIONS = {
    "default": "default",
    "low": "fast responses with lighter reasoning",
    "medium": "balances speed and reasoning depth for everyday tasks",
    "high": "greater reasoning depth for complex problems",
    "xhigh": "extra high reasoning depth for complex problems",
}
MODEL_LABELS = {
    "default": "default",
    "gpt-5.5": "gpt-5.5",
    "gpt-5.4": "gpt-5.4",
    "gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.3": "gpt-5.3",
}
MODEL_DESCRIPTIONS = {
    "default": "default",
    "gpt-5.5": "high-capability general model",
    "gpt-5.4": "balanced general model",
    "gpt-5.4-mini": "small, fast, and cost-efficient model for simpler coding tasks",
    "gpt-5.3": "older general model",
}
CODEX_YOLO = os.environ.get("CODEX_YOLO", "1").strip().lower() in {"1", "true", "yes", "on"}
CODEX_TIMEOUT_SECONDS = int(os.environ.get("CODEX_TIMEOUT_SECONDS", "900"))
CODEX_PROGRESS_SECONDS = int(os.environ.get("CODEX_PROGRESS_SECONDS", "30"))
TELEGRAM_PROGRESS_UPDATE_SECONDS = int(os.environ.get("TELEGRAM_PROGRESS_UPDATE_SECONDS", "5"))
POLL_TIMEOUT_SECONDS = int(os.environ.get("TELEGRAM_POLL_TIMEOUT_SECONDS", "50"))
MEDIA_GROUP_DELAY_SECONDS = float(os.environ.get("TELEGRAM_MEDIA_GROUP_DELAY_SECONDS", "1.0"))
INLINE_FILE_MAX_BYTES = int(os.environ.get("TELEGRAM_INLINE_FILE_MAX_BYTES", "200000"))
ARTIFACT_TELEGRAM_MAX_BYTES = int(os.environ.get("TELEGRAM_ARTIFACT_MAX_BYTES", "10000000"))
GCS_ARTIFACT_BUCKET = os.environ.get("GCS_ARTIFACT_BUCKET", "").strip()
GCS_ARTIFACT_PREFIX = os.environ.get("GCS_ARTIFACT_PREFIX", "codex-artifacts").strip().strip("/")
GCS_SIGNED_URL_DURATION = os.environ.get("GCS_SIGNED_URL_DURATION", "15m").strip()
GCS_SIGNING_SERVICE_ACCOUNT = os.environ.get("GCS_SIGNING_SERVICE_ACCOUNT", "").strip()
CODEX_STYLE_PREFIX = os.environ.get(
    "CODEX_STYLE_PREFIX",
    "Answer in caveman full by default. Preserve user's dominant language. Keep replies terse, factual, and direct. For mission-critical cmd or code work, report in formatted sections with a label line like COMMAND or RESULT, then the command or output body on the next lines.",
).strip()
CODEX_UPLOAD_CONTRACT = (
    "When user asks to send, upload, attach, share, or provide a local file, decide the right delivery. "
    "If a Telegram or GCS upload is needed, emit a control block at the end exactly like:\n"
    "UPLOAD\n"
    "path: /absolute/local/file\n"
    "target: telegram|gcs|auto\n"
    "mode: photo|document|auto\n"
    "Use target telegram for chat upload, gcs for downloadable link, auto if unsure. "
    "Use mode document when user says attachment/document/file; photo for image preview. "
    "Only request upload for existing local files under the workspace, home, or /tmp. Repeat UPLOAD blocks for multiple files."
)
HANDOFF_DIR = Path(os.environ.get("TELEGRAM_HANDOFF_DIR", "/tmp/handoff"))

API_BASE = f"https://api.telegram.org/bot{TOKEN}"
work_queue: "queue.Queue[dict]" = queue.Queue()
REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = Path(os.environ.get("TELEGRAM_BOT_BASE_DIR", str(Path.home() / ".local/share/telegram-codex-bot")))
IMAGE_DIR = Path(os.environ.get("TELEGRAM_IMAGE_DIR", str(BASE_DIR / "generated")))
UPLOAD_DIR = Path(os.environ.get("TELEGRAM_UPLOAD_DIR", str(BASE_DIR / "uploads")))
BUILTIN_IMAGE_ROOT = Path(os.environ.get("CODEX_GENERATED_IMAGE_ROOT", str(Path.home() / ".codex/generated_images")))
STATE_PATH = Path(os.environ.get("TELEGRAM_STATE_PATH", str(BASE_DIR / "state.json")))
CODEX_SESSION_ROOT = Path(os.environ.get("CODEX_SESSION_ROOT", str(Path.home() / ".codex/sessions")))
OFFSET_PATH = STATE_PATH.with_name("telegram_offset.json")
RESTART_NOTIFY_PATH = STATE_PATH.with_name("restart_notify.json")
RESTART_NOTIFY_MAX_AGE_SECONDS = int(os.environ.get("TELEGRAM_RESTART_NOTIFY_MAX_AGE_SECONDS", "3600"))
state_lock = threading.Lock()
state = {"model": CODEX_MODEL_DEFAULT, "reasoning": CODEX_REASONING_DEFAULT}
topic_state: dict[str, dict[str, str]] = {}
media_group_lock = threading.Lock()
media_group_buffers: dict[str, dict] = {}


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def request_json(method: str, data: dict | None = None) -> dict:
    if data is None:
        data = {}
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"{API_BASE}/{method}", data=encoded)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT_SECONDS + 15) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        retry_after = 0
        try:
            payload = json.loads(body)
            retry_after = int((payload.get("parameters") or {}).get("retry_after") or 0)
        except (ValueError, json.JSONDecodeError):
            payload = {}
        if exc.code == 429 and retry_after > 0:
            log(f"telegram rate limited method={method} retry_after={retry_after}")
            time.sleep(min(retry_after, 30))
        raise RuntimeError(f"Telegram {method} HTTP {exc.code}: {body or exc.reason}")
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {payload}")
    return payload


def set_bot_commands() -> None:
    if not ALLOWED_IDS:
        request_json("deleteMyCommands", {})
        return
    base_commands = [
        {"command": "start", "description": "Show help"},
        {"command": "help", "description": "Show help"},
        {"command": "status", "description": "Show bot status"},
        {"command": "agent", "description": "Create a topic/session"},
        {"command": "model", "description": "Choose Codex model"},
        {"command": "reason", "description": "Choose reasoning effort"},
        {"command": "plan", "description": "Plan this topic"},
        {"command": "recap", "description": "One-line session recap"},
        {"command": "sessions", "description": "Show sessions and agents"},
        {"command": "topicname", "description": "Set current topic name"},
        {"command": "handoff", "description": "Create session handoff"},
        {"command": "reload", "description": "Reload topic session"},
        {"command": "clear", "description": "Clear topic session"},
        {"command": "delete", "description": "Delete this topic"},
        {"command": "image", "description": "Generate an image"},
        {"command": "lastimage", "description": "Send latest image"},
        {"command": "images", "description": "List generated images"},
        {"command": "id", "description": "Show your Telegram user id"},
    ]
    owner_commands = json.dumps(
        [
            *base_commands[:9],
            {"command": "restart", "description": "Show restart button"},
            *base_commands[9:],
        ]
    )
    group_commands = json.dumps(base_commands)
    for user_id in ALLOWED_IDS:
        request_json(
            "setMyCommands",
            {
                "scope": json.dumps({"type": "chat", "chat_id": int(user_id)}),
                "commands": owner_commands,
            },
        )
    for chat_id in ALLOWED_CHAT_IDS:
        request_json(
            "setMyCommands",
            {
                "scope": json.dumps({"type": "chat", "chat_id": int(chat_id)}),
                "commands": group_commands,
            },
        )


def request_openai_json(path: str, payload: dict) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set, so /image cannot use the OpenAI image model.")
    req = urllib.request.Request(
        f"https://api.openai.com/v1/{path.lstrip('/')}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=CODEX_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode())


def download_telegram_file(file_id: str) -> Path:
    result = request_json("getFile", {"file_id": file_id})["result"]
    file_path = result["file_path"]
    suffix = Path(file_path).suffix or ".jpg"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / f"{int(time.time() * 1000)}-{Path(file_path).stem}{suffix}"
    url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    with urllib.request.urlopen(url, timeout=POLL_TIMEOUT_SECONDS + 30) as response:
        local_path.write_bytes(response.read())
    local_path.chmod(0o600)
    return local_path


def downloaded_file_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > INLINE_FILE_MAX_BYTES:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text


def load_state() -> None:
    global state
    if not STATE_PATH.exists():
        return
    try:
        loaded = json.loads(STATE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return
    with state_lock:
        state.update({key: value for key, value in loaded.items() if isinstance(value, str)})


def save_state() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with state_lock:
        payload = json.dumps(state, indent=2, sort_keys=True)
    STATE_PATH.write_text(payload + "\n")
    STATE_PATH.chmod(0o600)


def load_update_offset() -> int | None:
    if not OFFSET_PATH.exists():
        return None
    try:
        payload = json.loads(OFFSET_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        offset = int(payload.get("offset") or 0)
    except (TypeError, ValueError):
        return None
    return offset or None


def save_update_offset(offset: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(json.dumps({"offset": int(offset)}, indent=2, sort_keys=True) + "\n")
    OFFSET_PATH.chmod(0o600)


def save_restart_notification(chat_id: int, thread_id: int | None = None) -> None:
    payload = {
        "chat_id": int(chat_id),
        "created_at": time.time(),
        "thread_id": int(thread_id) if thread_id is not None else None,
    }
    RESTART_NOTIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESTART_NOTIFY_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    RESTART_NOTIFY_PATH.chmod(0o600)
    log(f"restart notification marker saved chat_id={chat_id} thread_id={thread_id}")


def pop_restart_notification() -> dict | None:
    if not RESTART_NOTIFY_PATH.exists():
        return None
    try:
        payload = json.loads(RESTART_NOTIFY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        payload = None
    try:
        RESTART_NOTIFY_PATH.unlink()
    except OSError:
        pass
    return payload if isinstance(payload, dict) else None


def send_restart_ready_notification() -> None:
    payload = pop_restart_notification()
    if not payload:
        return
    try:
        created_at = float(payload.get("created_at") or 0)
        age = time.time() - created_at if created_at else 0
        if created_at and age > RESTART_NOTIFY_MAX_AGE_SECONDS:
            log(f"restart ready notification skipped stale age={age:.0f}s")
            return
        chat_id = int(payload["chat_id"])
        thread_id = payload.get("thread_id")
        send_message(chat_id, "codexlav is ready", int(thread_id) if thread_id is not None else None)
        log(f"restart ready notification sent chat_id={chat_id} thread_id={thread_id}")
    except Exception as exc:
        log(f"restart ready notification failed error={exc}")


def topic_key(chat_id: int, thread_id: int | None) -> str:
    if thread_id is None:
        return f"{chat_id}:root"
    return f"{chat_id}:{thread_id}"


def load_topic_state() -> None:
    global topic_state
    path = STATE_PATH.with_name("topic_state.json")
    if not path.exists():
        return
    try:
        loaded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(loaded, dict):
        topic_state = {
            str(key): value
            for key, value in loaded.items()
            if isinstance(value, dict)
        }


def save_topic_state() -> None:
    path = STATE_PATH.with_name("topic_state.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(topic_state, indent=2, sort_keys=True)
    path.write_text(payload + "\n")
    path.chmod(0o600)


def get_topic_session(chat_id: int, thread_id: int | None) -> str:
    with state_lock:
        entry = topic_state.get(topic_key(chat_id, thread_id), {})
        return str(entry.get("session_id", "")).strip()


def set_topic_session(chat_id: int, thread_id: int | None, session_id: str) -> None:
    key = topic_key(chat_id, thread_id)
    with state_lock:
        entry = topic_state.get(key, {})
        entry["session_id"] = session_id
        entry["mode"] = entry.get("mode", "chat")
        topic_state[key] = entry
    save_topic_state()


def clear_topic_session(chat_id: int, thread_id: int | None) -> None:
    key = topic_key(chat_id, thread_id)
    with state_lock:
        entry = topic_state.get(key, {})
        entry.pop("session_id", None)
        if entry:
            topic_state[key] = entry
        else:
            topic_state.pop(key, None)
    save_topic_state()


def delete_topic_state(chat_id: int, thread_id: int | None) -> dict:
    with state_lock:
        entry = topic_state.pop(topic_key(chat_id, thread_id), {})
    save_topic_state()
    return entry


def archive_codex_session(session_id: str) -> str:
    session_id = session_id.strip()
    if not session_id:
        return ""
    proc = subprocess.run(
        ["codex", "archive", session_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=CODEX_CWD,
        timeout=CODEX_TIMEOUT_SECONDS,
    )
    output = (proc.stdout.strip() or proc.stderr.strip() or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(output or f"codex archive exited with {proc.returncode}")
    return output


def archive_topic_session(entry: dict) -> str:
    session_id = str(entry.get("session_id", "")).strip()
    if not session_id:
        return ""
    return archive_codex_session(session_id)


def set_topic_metadata(
    chat_id: int,
    thread_id: int | None,
    chat_name: str | None = None,
    topic_name: str | None = None,
) -> None:
    key = topic_key(chat_id, thread_id)
    with state_lock:
        entry = topic_state.get(key, {})
        if chat_name:
            entry["chat_name"] = chat_name[:128]
        if topic_name:
            entry["topic_name"] = topic_name[:128]
        if entry:
            topic_state[key] = entry
    save_topic_state()


def set_topic_recap(chat_id: int, thread_id: int | None, recap: str) -> None:
    key = topic_key(chat_id, thread_id)
    with state_lock:
        entry = topic_state.get(key, {})
        entry["recap"] = recap[:1000]
        topic_state[key] = entry
    save_topic_state()


def set_topic_name(chat_id: int, thread_id: int | None, name: str) -> None:
    set_topic_metadata(chat_id, thread_id, topic_name=name.strip()[:128])


def set_topic_mode(chat_id: int, thread_id: int | None, mode: str) -> None:
    key = topic_key(chat_id, thread_id)
    with state_lock:
        entry = topic_state.get(key, {})
        entry["mode"] = mode
        topic_state[key] = entry
    save_topic_state()


def get_topic_mode(chat_id: int, thread_id: int | None) -> str:
    with state_lock:
        entry = topic_state.get(topic_key(chat_id, thread_id), {})
        return str(entry.get("mode", "chat")).strip() or "chat"


def current_model(chat_id: int | None = None, thread_id: int | None = None) -> str:
    if chat_id is not None:
        with state_lock:
            entry = topic_state.get(topic_key(chat_id, thread_id), {})
            selected = str(entry.get("model", "")).strip()
            if selected:
                return selected
    with state_lock:
        return state.get("model", "").strip()


def set_current_model(model: str, chat_id: int | None = None, thread_id: int | None = None) -> None:
    normalized = "" if model == "default" else model
    if chat_id is not None:
        key = topic_key(chat_id, thread_id)
        with state_lock:
            entry = topic_state.get(key, {})
            if normalized:
                entry["model"] = normalized
            else:
                entry.pop("model", None)
            topic_state[key] = entry
        save_topic_state()
        return
    with state_lock:
        state["model"] = normalized
    save_state()


def current_reasoning(chat_id: int | None = None, thread_id: int | None = None) -> str:
    if chat_id is not None:
        with state_lock:
            entry = topic_state.get(topic_key(chat_id, thread_id), {})
            selected = str(entry.get("reasoning", "")).strip()
            if selected:
                return selected
    with state_lock:
        return state.get("reasoning", "").strip()


def set_current_reasoning(reasoning: str, chat_id: int | None = None, thread_id: int | None = None) -> None:
    normalized = "" if reasoning == "default" else reasoning
    if chat_id is not None:
        key = topic_key(chat_id, thread_id)
        with state_lock:
            entry = topic_state.get(key, {})
            if normalized:
                entry["reasoning"] = normalized
            else:
                entry.pop("reasoning", None)
            topic_state[key] = entry
        save_topic_state()
        return
    with state_lock:
        state["reasoning"] = normalized
    save_state()


def model_label(model: str | None = None, chat_id: int | None = None, thread_id: int | None = None) -> str:
    selected = current_model(chat_id, thread_id) if model is None else model
    return selected or "default"


def reasoning_label(reasoning: str | None = None, chat_id: int | None = None, thread_id: int | None = None) -> str:
    selected = current_reasoning(chat_id, thread_id) if reasoning is None else reasoning
    return selected or "default"


def model_options_keyboard(chat_id: int, thread_id: int | None) -> str:
    rows = []
    for option in CODEX_MODEL_OPTIONS:
        value = "" if option == "default" else option
        selected = " *" if model_label(value) == model_label(chat_id=chat_id, thread_id=thread_id) else ""
        description = MODEL_DESCRIPTIONS.get(option, "")
        button_text = f"{option}{selected}"
        if description and description != option:
            button_text = f"{button_text} - {description}"
        rows.append(
            [
                {
                    "text": button_text,
                    "callback_data": f"model:{option}",
                }
            ]
        )
    rows.append(
        [
            {
                "text": f"Reasoning: {reasoning_label(chat_id=chat_id, thread_id=thread_id)}",
                "callback_data": "model_menu:reasoning",
            }
        ]
    )
    return json.dumps({"inline_keyboard": rows})


def reasoning_options_keyboard(chat_id: int, thread_id: int | None) -> str:
    rows = []
    for option in ["default", *REASONING_OPTIONS]:
        value = "" if option == "default" else option
        selected = " *" if reasoning_label(value) == reasoning_label(chat_id=chat_id, thread_id=thread_id) else ""
        description = REASONING_DESCRIPTIONS.get(option, "")
        button_text = f"{option}{selected}"
        if description and description != option:
            button_text = f"{button_text} - {description}"
        rows.append(
            [
                {
                    "text": button_text,
                    "callback_data": f"reasoning:{option}",
                }
            ]
        )
    rows.append([{"text": "Back to models", "callback_data": "reasoning_menu:model"}])
    return json.dumps({"inline_keyboard": rows})


def send_model_menu(chat_id: int, thread_id: int | None = None) -> None:
    request_json(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
            "text": (
                f"Current model: {model_label(chat_id=chat_id, thread_id=thread_id)}\n"
                f"Current reasoning: {reasoning_label(chat_id=chat_id, thread_id=thread_id)}\n"
                "Choose a model:"
            ),
            "reply_markup": model_options_keyboard(chat_id, thread_id),
        },
    )


def send_reasoning_menu(chat_id: int, thread_id: int | None = None) -> None:
    request_json(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
            "text": (
                f"Current model: {model_label(chat_id=chat_id, thread_id=thread_id)}\n"
                f"Current reasoning: {reasoning_label(chat_id=chat_id, thread_id=thread_id)}\n"
                "Choose a reasoning level:"
            ),
            "reply_markup": reasoning_options_keyboard(chat_id, thread_id),
        },
    )


def send_restart_button(chat_id: int, thread_id: int | None = None) -> None:
    if chat_id < 0:
        targets = OWNER_USER_IDS or ALLOWED_IDS
        for owner_id in targets:
            send_restart_button(int(owner_id), None)
        send_message(chat_id, "Restart button sent to owner private chat.", thread_id)
        return
    save_restart_notification(chat_id, thread_id)
    request_json(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
            "text": "Bot update finished. Restart when ready.",
            "reply_markup": json.dumps(
                {"inline_keyboard": [[{"text": "Restart bot", "callback_data": "bot_restart"}]]}
            ),
        },
    )


def send_sessions_button(chat_id: int, thread_id: int | None = None) -> None:
    request_json(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
            "text": "Sessions",
            "reply_markup": json.dumps(
                {"inline_keyboard": [[{"text": "Show sessions / agents", "callback_data": "sessions:recap"}]]}
            ),
        },
    )


def generated_image_files(limit: int = 10) -> list[Path]:
    if not BUILTIN_IMAGE_ROOT.exists():
        return []
    files = [path for path in BUILTIN_IMAGE_ROOT.rglob("*.png") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def generated_image_keyboard(limit: int = 10) -> str:
    rows = []
    for index, path in enumerate(generated_image_files(limit), start=1):
        age_seconds = max(0, int(time.time() - path.stat().st_mtime))
        if age_seconds < 60:
            age = f"{age_seconds}s ago"
        elif age_seconds < 3600:
            age = f"{age_seconds // 60}m ago"
        else:
            age = f"{age_seconds // 3600}h ago"
        rows.append(
            [
                {
                    "text": f"{index}. {path.name[:18]} ({age})",
                    "callback_data": f"send_builtin_image:{index - 1}",
                }
            ]
        )
    return json.dumps({"inline_keyboard": rows})


def send_generated_image_menu(chat_id: int, thread_id: int | None = None) -> None:
    images = generated_image_files()
    if not images:
        send_message(chat_id, "No built-in generated images found yet.", thread_id=thread_id)
        return
    request_json(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
            "text": "Choose a built-in generated image to send:",
            "reply_markup": generated_image_keyboard(),
        },
    )


def send_latest_generated_image(chat_id: int, thread_id: int | None = None) -> None:
    images = generated_image_files(1)
    if not images:
        send_message(chat_id, "No built-in generated images found yet.", thread_id=thread_id)
        return
    send_photo(chat_id, images[0], f"Built-in image_gen output: {images[0].name}", thread_id=thread_id)


def answer_callback(callback_query_id: str, text: str = "") -> None:
    data = {"callback_query_id": callback_query_id}
    if text:
        data["text"] = text
    request_json("answerCallbackQuery", data)


def request_multipart(method: str, fields: dict[str, str], files: dict[str, Path]) -> dict:
    boundary = f"----telegram-codex-{int(time.time() * 1000)}"
    body = bytearray()

    def add_part(name: str, headers: list[str], content: bytes) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"'.encode())
        for header in headers:
            body.extend(f"; {header}".encode())
        body.extend(b"\r\n")
        body.extend(b"\r\n")
        body.extend(content)
        body.extend(b"\r\n")

    for name, value in fields.items():
        add_part(name, [], value.encode())
    for name, path in files.items():
        add_part(
            name,
            [f'filename="{path.name}"', "Content-Type: image/png"],
            path.read_bytes(),
        )

    body.extend(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{API_BASE}/{method}",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT_SECONDS + 30) as response:
        payload = json.loads(response.read().decode())
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {payload}")
    return payload


def upload_gcs_artifact(file_path: Path) -> str:
    if not GCS_ARTIFACT_BUCKET:
        raise RuntimeError("GCS_ARTIFACT_BUCKET is not set.")
    object_name = f"{GCS_ARTIFACT_PREFIX}/{int(time.time())}-{file_path.name}"
    object_uri = f"gs://{GCS_ARTIFACT_BUCKET}/{object_name}"
    sign_base = ["gcloud", "storage", "sign-url", object_uri, f"--duration={GCS_SIGNED_URL_DURATION}"]
    if GCS_SIGNING_SERVICE_ACCOUNT:
        sign_base.append(f"--impersonate-service-account={GCS_SIGNING_SERVICE_ACCOUNT}")

    upload_sign = subprocess.run(
        [
            *sign_base[:3],
            "--http-verb=PUT",
            "--headers=content-type=application/octet-stream",
            *sign_base[3:],
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=CODEX_CWD,
        timeout=CODEX_TIMEOUT_SECONDS,
    )
    if upload_sign.returncode != 0:
        raise RuntimeError(
            "GCS upload URL failed:\n"
            f"{upload_sign.stderr.strip() or upload_sign.stdout.strip() or '(empty)'}"
        )
    upload_url = ""
    for line in upload_sign.stdout.splitlines():
        if line.startswith("signed_url:"):
            upload_url = line.split(":", 1)[1].strip()
            break
    if not upload_url.startswith("http"):
        raise RuntimeError(f"GCS upload URL returned no URL: {upload_url or '(empty)'}")
    put = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--request",
            "PUT",
            "--upload-file",
            str(file_path),
            "--header",
            "Content-Type: application/octet-stream",
            upload_url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=CODEX_CWD,
        timeout=CODEX_TIMEOUT_SECONDS,
    )
    if put.returncode != 0:
        raise RuntimeError(
            "GCS upload failed:\n"
            f"{put.stderr.strip() or put.stdout.strip() or '(empty)'}"
        )
    sign = subprocess.run(
        sign_base,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=CODEX_CWD,
        timeout=CODEX_TIMEOUT_SECONDS,
    )
    if sign.returncode != 0:
        raise RuntimeError(
            "GCS sign-url failed:\n"
            f"{sign.stderr.strip() or sign.stdout.strip() or '(empty)'}"
        )
    signed_url = ""
    for line in sign.stdout.splitlines():
        if line.startswith("signed_url:"):
            signed_url = line.split(":", 1)[1].strip()
            break
    if not signed_url.startswith("http"):
        raise RuntimeError(f"GCS sign-url returned no URL: {signed_url or '(empty)'}")
    return signed_url


def send_message(chat_id: int, text: str, thread_id: int | None = None) -> list[int]:
    if should_format_bot_message(text):
        ids = send_formatted_message(chat_id, text, thread_id)
        log(f"sent formatted message chat_id={chat_id} thread_id={thread_id} chunks={len(ids)} chars={len(text)}")
        return ids
    chunks = split_for_telegram(text)
    message_ids = []
    for chunk in chunks:
        try:
            payload = request_json(
                "sendMessage",
                {
                    "chat_id": str(chat_id),
                    **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
                    "text": chunk,
                    "disable_web_page_preview": "true",
                },
            )
        except Exception as exc:
            log(f"send message failed chat_id={chat_id} thread_id={thread_id} error={exc}")
            break
        result = payload.get("result") or {}
        if result.get("message_id") is not None:
            message_ids.append(int(result["message_id"]))
    log(f"sent message chat_id={chat_id} thread_id={thread_id} chunks={len(chunks)} chars={len(text)}")
    return message_ids


def should_format_bot_message(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if "```" in stripped:
        return True
    return any(normalized_section_header(line) for line in stripped.splitlines())


def send_placeholder(chat_id: int, thread_id: int | None, text: str = "Working...") -> int | None:
    ids = send_message(chat_id, text, thread_id)
    return ids[-1] if ids else None


def edit_message(chat_id: int, message_id: int | None, text: str) -> bool:
    if message_id is None:
        return False
    try:
        payload = {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "text": text[:3900] or "(no output)",
            "disable_web_page_preview": "true",
        }
        if should_format_bot_message(text):
            payload["text"] = pack_html_blocks(render_output_html_blocks(text), max_len=3900)[0] or "(no output)"
            payload["parse_mode"] = "HTML"
        request_json(
            "editMessageText",
            payload,
        )
        log(f"edited message chat_id={chat_id} message_id={message_id} chars={len(text)}")
        return True
    except Exception as exc:
        log(f"edit message failed chat_id={chat_id} message_id={message_id} error={exc}")
        return False


def delete_message(chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        request_json("deleteMessage", {"chat_id": str(chat_id), "message_id": str(message_id)})
        log(f"deleted message chat_id={chat_id} message_id={message_id}")
    except Exception as exc:
        log(f"delete message failed chat_id={chat_id} message_id={message_id} error={exc}")


def finish_text_response(chat_id: int, thread_id: int | None, status_message_id: int | None, text: str) -> None:
    if should_format_bot_message(text):
        delete_message(chat_id, status_message_id)
        send_formatted_message(chat_id, text, thread_id)
        return
    chunks = split_for_telegram(text)
    if len(chunks) == 1 and edit_message(chat_id, status_message_id, chunks[0]):
        return
    delete_message(chat_id, status_message_id)
    send_formatted_message(chat_id, text, thread_id)


def enqueue_work(item: dict, status_text: str = "Working...") -> None:
    item["status_message_id"] = send_placeholder(item["chat_id"], item.get("thread_id"), status_text)
    work_queue.put(item)


def send_photo(chat_id: int, image_path: Path, caption: str = "", thread_id: int | None = None) -> None:
    fields = {"chat_id": str(chat_id)}
    if thread_id is not None:
        fields["message_thread_id"] = str(int(thread_id))
    if caption:
        fields["caption"] = caption
    request_multipart("sendPhoto", fields, {"photo": image_path})
    log(f"sent photo chat_id={chat_id} thread_id={thread_id} path={image_path}")


def send_document(chat_id: int, file_path: Path, caption: str = "", thread_id: int | None = None) -> None:
    fields = {"chat_id": str(chat_id)}
    if thread_id is not None:
        fields["message_thread_id"] = str(int(thread_id))
    if caption:
        fields["caption"] = caption
    request_multipart("sendDocument", fields, {"document": file_path})
    log(f"sent document chat_id={chat_id} thread_id={thread_id} path={file_path}")


def create_forum_topic(chat_id: int, name: str) -> int:
    payload = request_json(
        "createForumTopic",
        {
            "chat_id": str(chat_id),
            "name": name[:128] or "Codex",
        },
    )["result"]
    thread_id = payload.get("message_thread_id")
    if thread_id is None:
        raise RuntimeError("createForumTopic returned no message_thread_id")
    return int(thread_id)


def delete_forum_topic(chat_id: int, thread_id: int) -> None:
    request_json(
        "deleteForumTopic",
        {
            "chat_id": str(chat_id),
            "message_thread_id": str(thread_id),
        },
    )


def split_for_telegram(text: str) -> list[str]:
    if not text:
        return ["(no output)"]
    max_len = 3900
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


SECTION_HEADERS = {"COMMAND", "RESULT", "ERROR", "WHERE", "NEXT", "SUMMARY"}


def normalized_section_header(line: str) -> str:
    stripped = line.strip()
    stripped = stripped.lstrip("#").strip()
    while len(stripped) >= 2 and stripped.startswith("*") and stripped.endswith("*"):
        stripped = stripped[1:-1].strip()
    stripped = stripped.rstrip(":").strip()
    upper = stripped.upper()
    return upper if upper in SECTION_HEADERS else ""


def escape_telegram_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_output_html_blocks(text: str) -> list[str]:
    if not text.strip():
        return ["<blockquote>(no output)</blockquote>"]

    blocks: list[str] = []
    quote_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False
    in_section_body = False

    def flush_quote() -> None:
        nonlocal quote_lines
        if not quote_lines:
            return
        content = "\n".join(quote_lines).strip()
        if content:
            blocks.append(f"<blockquote>{escape_telegram_html(content)}</blockquote>")
        quote_lines = []

    def flush_code() -> None:
        nonlocal code_lines
        if not code_lines:
            return
        code = escape_telegram_html("\n".join(code_lines).rstrip())
        blocks.append(f"<pre><code>{code}</code></pre>")
        code_lines = []

    def flush_section_body() -> None:
        nonlocal in_section_body
        if not in_section_body:
            return
        flush_code()
        in_section_body = False

    for line in text.rstrip().splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_quote()
                flush_section_body()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        section_header = normalized_section_header(stripped)
        if section_header:
            flush_quote()
            flush_section_body()
            blocks.append(f"<b>{escape_telegram_html(section_header)}</b>")
            in_section_body = True
            continue
        if not stripped:
            flush_quote()
            flush_section_body()
            continue
        if in_section_body:
            code_lines.append(line)
            continue
        quote_lines.append(line)

    if in_code:
        flush_code()
    flush_section_body()
    flush_quote()
    return blocks or ["<blockquote>(no output)</blockquote>"]


def pack_html_blocks(blocks: list[str], max_len: int = 3900) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if not current:
            current = block
            continue
        if len(current) + 1 + len(block) <= max_len:
            current += "\n" + block
        else:
            chunks.append(current)
            current = block
    if current:
        chunks.append(current)
    return chunks or ["<blockquote>(no output)</blockquote>"]


def send_formatted_message(chat_id: int, text: str, thread_id: int | None = None) -> list[int]:
    chunks = pack_html_blocks(render_output_html_blocks(text))
    message_ids = []
    for chunk in chunks:
        try:
            payload = request_json(
                "sendMessage",
                {
                    "chat_id": str(chat_id),
                    **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
            )
        except Exception as exc:
            log(f"send formatted message failed chat_id={chat_id} thread_id={thread_id} error={exc}")
            break
        result = payload.get("result") or {}
        if result.get("message_id") is not None:
            message_ids.append(int(result["message_id"]))
    return message_ids


def is_allowed(user_id: int) -> bool:
    return str(user_id) in ALLOWED_IDS


def is_owner(user_id: int) -> bool:
    if OWNER_USER_IDS:
        return str(user_id) in OWNER_USER_IDS
    return len(ALLOWED_IDS) == 1 and str(user_id) in ALLOWED_IDS


def is_allowed_chat(chat_id: int) -> bool:
    if chat_id > 0:
        return True
    return str(chat_id) in ALLOWED_CHAT_IDS


def current_queue_depth() -> int:
    return work_queue.qsize()


def ascii_bar(percent: float, width: int = 20) -> str:
    pct = max(0.0, min(100.0, percent))
    filled = int(round((pct / 100.0) * width))
    filled = max(0, min(width, filled))
    return "[" + "#" * filled + "." * (width - filled) + f"] {pct:.1f}%"


def codex_session_file(session_id: str | None = None) -> Path | None:
    selected = (session_id or CODEX_SESSION_ID).strip()
    if not selected or not CODEX_SESSION_ROOT.exists():
        return None
    matches = list(CODEX_SESSION_ROOT.rglob(f"*{selected}*.jsonl"))
    if matches:
        matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return matches[0]
    return None


def infer_session_id_from_file(path: Path | None) -> str:
    if path is None:
        return ""
    stem = path.stem
    match = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27,})", stem)
    if match:
        return match.group(1)
    return ""


def load_codex_token_usage(session_id: str | None = None) -> dict[str, int] | None:
    session_file = codex_session_file(session_id)
    if session_file is None:
        return None
    last_payload = None
    try:
        with session_file.open() as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload") or {}
                if record.get("type") == "event_msg" and payload.get("type") == "token_count":
                    last_payload = payload.get("info") or {}
    except OSError:
        return None
    if not last_payload:
        return None
    total = last_payload.get("total_token_usage") or {}
    last = last_payload.get("last_token_usage") or {}
    return {
        "total_input_tokens": int(total.get("input_tokens", 0) or 0),
        "total_cached_input_tokens": int(total.get("cached_input_tokens", 0) or 0),
        "total_output_tokens": int(total.get("output_tokens", 0) or 0),
        "total_reasoning_output_tokens": int(total.get("reasoning_output_tokens", 0) or 0),
        "total_tokens": int(total.get("total_tokens", 0) or 0),
        "last_input_tokens": int(last.get("input_tokens", 0) or 0),
        "last_cached_input_tokens": int(last.get("cached_input_tokens", 0) or 0),
        "last_output_tokens": int(last.get("output_tokens", 0) or 0),
        "last_reasoning_output_tokens": int(last.get("reasoning_output_tokens", 0) or 0),
        "last_total_tokens": int(last.get("total_tokens", 0) or 0),
        "model_context_window": int(last_payload.get("model_context_window", 0) or 0),
    }


def latest_codex_rate_limits() -> dict | None:
    if not CODEX_SESSION_ROOT.exists():
        return None
    files = [path for path in CODEX_SESSION_ROOT.rglob("*.jsonl") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files[:20]:
        latest = None
        try:
            with path.open() as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = record.get("payload") or {}
                    if record.get("type") != "event_msg" or payload.get("type") != "token_count":
                        continue
                    rate_limits = payload.get("rate_limits")
                    if isinstance(rate_limits, dict):
                        latest = rate_limits
        except OSError:
            continue
        if latest:
            return latest
    return None


def format_reset_time(epoch_seconds: int | float | None) -> str:
    if not epoch_seconds:
        return "unknown"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(epoch_seconds)))


def usage_bar(available_percent: float, width: int = 10) -> str:
    pct = max(0.0, min(100.0, available_percent))
    filled_exact = pct / 100.0 * width
    filled = int(filled_exact)
    partial = filled < width and filled_exact - filled >= 0.25
    empty = width - filled - (1 if partial else 0)
    return "█" * filled + ("▒" if partial else "") + "░" * max(0, empty)


def format_rate_limit(name: str, data: dict | None) -> str:
    if not isinstance(data, dict):
        return f"{name}: unavailable"
    used = float(data.get("used_percent") or 0.0)
    remaining = max(0.0, min(100.0, 100.0 - used))
    reset = format_reset_time(data.get("resets_at"))
    return f"{name:<7} {usage_bar(remaining)} {remaining:5.1f}% available ({used:.1f}% used, resets {reset})"


def codex_rate_limit_status() -> str:
    rate_limits = latest_codex_rate_limits()
    if not rate_limits:
        return "Codex usage: unavailable\n"
    primary = rate_limits.get("primary")
    secondary = rate_limits.get("secondary")
    lines = [
        format_rate_limit("5h slot", primary),
        format_rate_limit("Weekly", secondary),
    ]
    credits = rate_limits.get("credits")
    if isinstance(credits, dict):
        balance = credits.get("balance")
        unlimited = credits.get("unlimited")
        lines.append(f"Credits: {'unlimited' if unlimited else balance or '0'}")
    return "\n".join(lines) + "\n"


def sessions_recap_text() -> str:
    entries = session_entries()
    if not entries:
        return "No sessions recorded."
    chat_names: dict[str, str] = {}
    for key, entry in entries:
        chat_id_text = key.split(":", 1)[0]
        chat_name = str(entry.get("chat_name", "")).strip()
        if chat_name:
            chat_names[chat_id_text] = chat_name
    bubbles = []
    for index, (key, entry) in enumerate(entries, start=1):
        session_id = str(entry.get("session_id", "")).strip() or "none"
        mode = str(entry.get("mode", "chat")).strip() or "chat"
        model = str(entry.get("model", "")).strip() or model_label()
        reasoning = str(entry.get("reasoning", "")).strip() or reasoning_label()
        chat_id_text, raw_topic = key.split(":", 1)
        chat_name = str(entry.get("chat_name", "")).strip() or chat_names.get(chat_id_text) or chat_id_text
        topic_name = str(entry.get("topic_name", "")).strip()
        if not topic_name:
            topic_name = "General" if raw_topic == "root" else f"Thread {raw_topic}"
        recap = str(entry.get("recap", "")).strip() or "Not generated"
        bubbles.append(
            "\n".join(
                [
                    f"Chat: {chat_name}",
                    f"Topic: {topic_name}",
                    f"Key: {key}",
                    f"Index: {index}",
                    f"Session: {session_id}",
                    f"Mode: {mode}",
                    f"Model: {model}",
                    f"Reasoning: {reasoning}",
                    f"Recap: {recap}",
                ]
            )
        )
    return "\n\n".join(bubbles)


def session_entries() -> list[tuple[str, dict]]:
    with state_lock:
        entries = list(topic_state.items())
    entries.sort(key=lambda item: item[0])
    return entries


def parse_topic_key(key: str) -> tuple[int, int | None]:
    chat_text, thread_text = key.split(":", 1)
    return int(chat_text), None if thread_text == "root" else int(thread_text)


def sessions_keyboard() -> str:
    rows = []
    for index, (key, entry) in enumerate(session_entries()):
        if not str(entry.get("session_id", "")).strip():
            continue
        raw_topic = key.split(":", 1)[1]
        title = str(entry.get("topic_name", "")).strip() or ("General" if raw_topic == "root" else f"Thread {raw_topic}")
        rows.append([{"text": f"Recap {index + 1}: {title[:28]}", "callback_data": f"session_recap:{index}"}])
    return json.dumps({"inline_keyboard": rows})


def send_sessions_recap(chat_id: int, thread_id: int | None = None) -> None:
    send_formatted_message(chat_id, sessions_recap_text(), thread_id)
    keyboard = sessions_keyboard()
    if json.loads(keyboard).get("inline_keyboard"):
        request_json(
            "sendMessage",
            {
                "chat_id": str(chat_id),
                **({"message_thread_id": int(thread_id)} if thread_id is not None else {}),
                "text": "Session actions",
                "reply_markup": keyboard,
            },
        )


def recap_prompt() -> str:
    return (
        "$recap\n"
        "Generate exactly one sentence summarizing the current Codex session. "
        "No bullets. No heading. Mention current work and next action if known."
    )


def codex_command(
    image_paths: list[Path] | None = None,
    json_output: bool = False,
    session_id: str | None = None,
    resume: bool = True,
    selected_model: str | None = None,
    selected_reasoning: str | None = None,
    enabled_features: list[str] | None = None,
) -> list[str]:
    cmd = ["codex", "exec"]
    for feature in enabled_features or []:
        cmd.extend(["--enable", feature])
    if json_output:
        cmd.append("--json")
    if resume:
        cmd.append("resume")
        if session_id:
            cmd.append(session_id)
        else:
            cmd.extend(["--last", "--all"])
    cmd.append("--skip-git-repo-check")
    selected_model = selected_model if selected_model is not None else current_model()
    if selected_model:
        cmd.extend(["--model", selected_model])
    selected_reasoning = selected_reasoning if selected_reasoning is not None else current_reasoning()
    if selected_reasoning:
        cmd.extend(["-c", f"model_reasoning_effort={selected_reasoning}"])
    if CODEX_YOLO:
        cmd.append("--yolo")
    for image_path in image_paths or []:
        cmd.extend(["-i", str(image_path)])
    cmd.append("-")
    return cmd


def run_codex(
    prompt: str,
    image_paths: list[Path] | None = None,
    session_id: str | None = None,
    resume: bool = True,
    selected_model: str | None = None,
    selected_reasoning: str | None = None,
    enabled_features: list[str] | None = None,
) -> str:
    prompt = apply_codex_style(prompt)
    cmd = codex_command(
        image_paths,
        session_id=session_id,
        resume=resume,
        selected_model=selected_model,
        selected_reasoning=selected_reasoning,
        enabled_features=enabled_features,
    )
    log(f"codex start images={len(image_paths or [])} prompt_chars={len(prompt)}")
    proc = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=CODEX_CWD,
        timeout=CODEX_TIMEOUT_SECONDS,
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    log(f"codex exit status={proc.returncode} stdout_chars={len(stdout)} stderr_chars={len(stderr)}")
    if proc.returncode != 0:
        cmd_text = " ".join(shlex.quote(part) for part in cmd)
        return (
            f"Codex exited with status {proc.returncode}.\n\n"
            f"Command: {cmd_text}\n\n"
            f"stderr:\n{stderr or '(empty)'}\n\n"
            f"stdout:\n{stdout or '(empty)'}"
        )
    if stdout:
        return stdout
    if stderr:
        return f"Codex completed with stderr only:\n{stderr}"
    return "(Codex completed with no final message.)"


def short_text(value: str, limit: int = 180) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def progress_from_event(event: dict) -> str | None:
    event_type = event.get("type")
    if event_type != "item.started":
        return None

    item = event.get("item") or {}
    item_type = item.get("type")
    if item_type != "command_execution":
        return None

    command = short_text(item.get("command") or "command")
    return f"COMMAND\n{command}"


def strip_embedded_sections(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    skip_command_body = False

    for line in lines:
        header = normalized_section_header(line)
        if header == "COMMAND":
            skip_command_body = True
            continue
        if header == "RESULT":
            skip_command_body = False
            continue
        if header:
            skip_command_body = False
            cleaned.append(header)
            continue
        if skip_command_body:
            if not line.strip():
                skip_command_body = False
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def format_execution_result(
    stdout: str,
    stderr: str,
    return_code: int | None = None,
    command: str | None = None,
) -> str:
    body = strip_embedded_sections(stdout)
    if not body:
        body = stderr.strip() or "(no output)"
    result_header = "RESULT"
    if return_code not in (None, 0):
        body = f"Command exited with {return_code}\n{body}"
    if command:
        return f"COMMAND\n{command}\n\n{result_header}\n{body}"
    return f"{result_header}\n{body}"


def run_codex_streaming(
    prompt: str,
    chat_id: int,
    thread_id: int | None = None,
    image_paths: list[Path] | None = None,
    session_id: str | None = None,
    resume: bool = True,
    status_message_id: int | None = None,
    selected_model: str | None = None,
    selected_reasoning: str | None = None,
) -> str:
    prompt = apply_codex_style(prompt)
    cmd = codex_command(
        image_paths,
        json_output=True,
        session_id=session_id,
        resume=resume,
        selected_model=selected_model,
        selected_reasoning=selected_reasoning,
    )
    log(f"codex stream start images={len(image_paths or [])} prompt_chars={len(prompt)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=CODEX_CWD,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    proc.stdin.write(prompt)
    proc.stdin.close()

    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
    selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.time() + CODEX_TIMEOUT_SECONDS
    next_heartbeat = time.time() + CODEX_PROGRESS_SECONDS
    next_progress_update = 0.0
    last_command: str | None = None
    final_messages: list[str] = []
    stderr_lines: list[str] = []

    while selector.get_map():
        now = time.time()
        if now > deadline:
            proc.kill()
            raise subprocess.TimeoutExpired(cmd, CODEX_TIMEOUT_SECONDS)
        timeout = max(1, min(5, next_heartbeat - now, deadline - now))
        events = selector.select(timeout)
        if not events:
            if time.time() >= next_heartbeat:
                if not edit_message(chat_id, status_message_id, "Codex is still running..."):
                    send_message(chat_id, "Codex is still running...", thread_id)
                next_heartbeat = time.time() + CODEX_PROGRESS_SECONDS
            continue

        for key, _ in events:
            line = key.fileobj.readline()
            if line == "":
                selector.unregister(key.fileobj)
                continue
            if key.data == "stderr":
                stderr_lines.append(line.rstrip())
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            progress = progress_from_event(event)
            if progress:
                now = time.time()
                if now >= next_progress_update:
                    if not edit_message(chat_id, status_message_id, progress):
                        send_message(chat_id, progress, thread_id)
                    next_progress_update = now + TELEGRAM_PROGRESS_UPDATE_SECONDS
                if progress.startswith("COMMAND\n"):
                    last_command = progress.split("\n", 1)[1].strip() or last_command
            item = event.get("item") or {}
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text") or ""
                if text:
                    final_messages.append(text)

    return_code = proc.wait()
    stderr = "\n".join(stderr_lines).strip()
    stdout = "\n\n".join(final_messages).strip()
    log(f"codex stream exit status={return_code} final_chars={len(stdout)} stderr_chars={len(stderr)}")
    if return_code != 0:
        cmd_text = " ".join(shlex.quote(part) for part in cmd)
        return (
            f"Codex exited with status {return_code}.\n\n"
            f"Command: {cmd_text}\n\n"
            f"stderr:\n{stderr or '(empty)'}\n\n"
            f"stdout:\n{stdout or '(empty)'}"
        )
    if stdout:
        return format_execution_result(stdout, stderr, return_code, command=last_command)
    if stderr:
        return format_execution_result("", stderr, return_code, command=last_command)
    return "RESULT\n(no output)"


def start_codex_session(
    prompt: str,
    image_paths: list[Path] | None = None,
    selected_model: str | None = None,
    selected_reasoning: str | None = None,
) -> tuple[str | None, str]:
    prompt = apply_codex_style(prompt)
    cmd = codex_command(
        image_paths,
        json_output=True,
        resume=False,
        selected_model=selected_model,
        selected_reasoning=selected_reasoning,
    )
    started_at = time.time()
    log(f"codex new-session start images={len(image_paths or [])} prompt_chars={len(prompt)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=CODEX_CWD,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    proc.stdin.write(prompt)
    proc.stdin.close()

    session_id = None
    final_messages: list[str] = []
    stderr_lines: list[str] = []
    for line in proc.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session_meta":
            payload = event.get("payload") or {}
            session_id = str(payload.get("id") or "").strip() or session_id
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text") or ""
            if text:
                final_messages.append(text)

    stderr = proc.stderr.read().strip()
    if stderr:
        stderr_lines.append(stderr)
    return_code = proc.wait()
    stdout = "\n\n".join(final_messages).strip()
    stderr_text = "\n".join(stderr_lines).strip()
    if not session_id:
        session_id = infer_session_id_from_file(newest_session_file_after(started_at))
    log(f"codex new-session exit status={return_code} session_id={session_id or 'unknown'}")
    if return_code != 0:
        cmd_text = " ".join(shlex.quote(part) for part in cmd)
        return None, (
            f"Codex exited with status {return_code}.\n\n"
            f"Command: {cmd_text}\n\n"
            f"stderr:\n{stderr_text or '(empty)'}\n\n"
            f"stdout:\n{stdout or '(empty)'}"
        )
    if stdout:
        return session_id, format_execution_result(stdout, stderr_text, return_code)
    if stderr_text:
        return session_id, format_execution_result("", stderr_text, return_code)
    return session_id, "RESULT\n(no output)"


def newest_session_file_after(started_at: float) -> Path | None:
    if not CODEX_SESSION_ROOT.exists():
        return None
    candidates: list[Path] = []
    for path in CODEX_SESSION_ROOT.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime >= started_at - 1:
                candidates.append(path)
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def generated_after(path: Path, started_at: float) -> bool:
    try:
        return path.stat().st_mtime >= started_at - 1
    except OSError:
        return False


def newest_generated_image_after(started_at: float) -> Path | None:
    for path in generated_image_files(25):
        if generated_after(path, started_at):
            return path
    return None


def extract_generated_image_path(output: str, started_at: float | None = None) -> Path | None:
    pattern = re.compile(r"(/[^\s]+?\.codex/generated_images/[^\s]+?\.png)")
    for match in pattern.finditer(output):
        path = Path(match.group(1))
        if path.exists() and (started_at is None or generated_after(path, started_at)):
            return path
    return None


def extract_artifact_path(output: str) -> Path | None:
    candidates = []
    allowed_roots = [Path(CODEX_CWD).expanduser().resolve(), Path.home().resolve(), Path("/tmp")]
    for match in re.finditer(r"(/[^\s'\"`<>]+)", output):
        raw = match.group(1).rstrip(".,;:)])}>")
        path = Path(raw)
        if not path.is_absolute() or not path.exists() or not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        candidates.append(resolved)
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def allowed_local_file(path: Path) -> Path | None:
    if not path.is_absolute() or not path.exists() or not path.is_file():
        return None
    try:
        resolved = path.resolve()
    except OSError:
        return None
    allowed_roots = [Path(CODEX_CWD).expanduser().resolve(), Path.home().resolve(), Path("/tmp")]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        return None
    return resolved


def parse_upload_blocks(text: str) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    cleaned: list[str] = []
    uploads: list[dict] = []
    index = 0
    headers = SECTION_HEADERS | {"UPLOAD"}

    while index < len(lines):
        if lines[index].strip().upper() != "UPLOAD":
            cleaned.append(lines[index])
            index += 1
            continue

        index += 1
        fields: dict[str, str] = {"target": "auto", "mode": "auto"}
        path_text = ""
        while index < len(lines):
            stripped = lines[index].strip()
            upper = stripped.upper()
            if upper in headers:
                break
            if not stripped:
                index += 1
                break
            key, sep, value = stripped.partition(":")
            if sep and key.strip().lower() in {"path", "target", "mode"}:
                fields[key.strip().lower()] = value.strip()
            elif not path_text:
                path_text = stripped.strip("`")
            index += 1

        raw_path = fields.get("path") or path_text
        file_path = allowed_local_file(Path(raw_path.strip("`"))) if raw_path else None
        if file_path is not None:
            fields["path"] = str(file_path)
            fields["target"] = fields.get("target", "auto").lower()
            fields["mode"] = fields.get("mode", "auto").lower()
            uploads.append(fields)

    return "\n".join(cleaned).strip(), uploads


def execute_upload_request(chat_id: int, thread_id: int | None, request: dict) -> None:
    file_path = allowed_local_file(Path(str(request.get("path") or "")))
    if file_path is None:
        return
    target = str(request.get("target") or "auto").lower()
    mode = str(request.get("mode") or "auto").lower()

    if target == "gcs":
        url = upload_gcs_artifact(file_path)
        send_message(chat_id, f"Artifact download: {url}", thread_id=thread_id)
        return

    if target == "telegram":
        if mode == "photo":
            send_photo(chat_id, file_path, f"Uploaded: {file_path.name}", thread_id)
        else:
            send_document(chat_id, file_path, f"Uploaded: {file_path.name}", thread_id)
        return

    if file_path.stat().st_size > ARTIFACT_TELEGRAM_MAX_BYTES:
        url = upload_gcs_artifact(file_path)
        send_message(chat_id, f"Artifact download: {url}", thread_id=thread_id)
        return
    if mode == "document":
        send_document(chat_id, file_path, f"Uploaded: {file_path.name}", thread_id)
        return
    if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        send_photo(chat_id, file_path, f"Uploaded: {file_path.name}", thread_id)
        return
    send_document(chat_id, file_path, f"Uploaded: {file_path.name}", thread_id)


def execute_upload_requests(chat_id: int, thread_id: int | None, requests: list[dict]) -> None:
    for request in requests:
        execute_upload_request(chat_id, thread_id, request)


def send_artifact(chat_id: int, file_path: Path, thread_id: int | None = None) -> None:
    if file_path.stat().st_size <= ARTIFACT_TELEGRAM_MAX_BYTES:
        try:
            send_document(chat_id, file_path, f"Codex artifact: {file_path.name}", thread_id=thread_id)
            return
        except Exception as exc:
            log(f"telegram document upload failed path={file_path} error={exc}")
    url = upload_gcs_artifact(file_path)
    send_message(chat_id, f"Artifact download: {url}", thread_id=thread_id)


def write_handoff_file(chat_id: int, thread_id: int | None, content: str) -> Path:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    safe_thread = str(thread_id) if thread_id is not None else "root"
    path = HANDOFF_DIR / f"handoff-{chat_id}-{safe_thread}-{int(time.time())}.md"
    body = content.strip()
    if not body.startswith("# "):
        body = "# Handoff\n\n" + body
    path.write_text(body + "\n")
    path.chmod(0o600)
    return path


def generate_builtin_codex_image(
    prompt: str,
    chat_id: int | None = None,
    thread_id: int | None = None,
    image_paths: list[Path] | None = None,
    selected_model: str | None = None,
    selected_reasoning: str | None = None,
) -> Path:
    started_at = time.time()
    clean_prompt = clean_image_prompt(prompt)
    if image_paths and clean_prompt == "abstract Codex avatar":
        clean_prompt = "Generate a new image based on the attached image."
    image_prompt = (
        "$imagegen "
        f"{clean_prompt}\n\n"
        "Generate a raster image with Codex built-in image generation. "
        "If image inputs are attached, use them as edit targets or visual references according to the prompt. "
        "After the image is generated, report the saved PNG file path only."
    )
    image_prompt = style_prompt(image_prompt)
    output = run_codex(
        image_prompt,
        image_paths=image_paths,
        resume=False,
        selected_model=selected_model,
        selected_reasoning=selected_reasoning,
        enabled_features=["imagegenext"],
    )
    if output.startswith("Codex exited with status"):
        raise RuntimeError(output)
    image_path = newest_generated_image_after(started_at) or extract_generated_image_path(output, started_at)
    if image_path is None:
        raise RuntimeError(f"Codex completed, but no generated PNG was found.\n\n{output}")
    return image_path


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    rows = []
    stride = width * 3
    for y in range(height):
        rows.append(b"\x00" + pixels[y * stride : (y + 1) * stride])
    raw = b"".join(rows)
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += png_chunk(b"IDAT", zlib.compress(raw, 9))
    data += png_chunk(b"IEND", b"")
    path.write_bytes(data)


def clean_image_prompt(text: str) -> str:
    cleaned = text.strip()
    if cleaned.lower().startswith("/image"):
        cleaned = cleaned[6:].strip()
    return cleaned or "abstract Codex avatar"


def apply_codex_style(prompt: str) -> str:
    prompt = prompt.strip()
    style_parts = [part for part in (CODEX_STYLE_PREFIX, CODEX_UPLOAD_CONTRACT) if part]
    if not style_parts:
        return prompt
    style = "\n".join(style_parts)
    if prompt.startswith(style):
        return prompt
    if CODEX_STYLE_PREFIX and prompt.startswith(CODEX_STYLE_PREFIX):
        return prompt.replace(CODEX_STYLE_PREFIX, style, 1)
    return f"{style}\n\n{prompt}"


def style_prompt(prompt: str) -> str:
    return apply_codex_style(prompt)


def normalized_command(text: str) -> str:
    if not text.startswith("/"):
        return text
    head, *tail = text.split(None, 1)
    command = head.split("@", 1)[0]
    if tail:
        return f"{command} {tail[0]}"
    return command


def command_name(command_text: str) -> str:
    return command_text.split(None, 1)[0] if command_text else ""


def message_thread_id(message: dict) -> int | None:
    direct = message.get("message_thread_id")
    if direct is not None:
        return int(direct)
    reply = message.get("reply_to_message") or {}
    reply_thread = reply.get("message_thread_id")
    if reply_thread is not None:
        return int(reply_thread)
    return None


def generate_ai_image(prompt: str) -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    clean_prompt = clean_image_prompt(prompt)
    result = request_openai_json(
        "images/generations",
        {
            "model": OPENAI_IMAGE_MODEL,
            "prompt": clean_prompt,
            "size": OPENAI_IMAGE_SIZE,
            "quality": OPENAI_IMAGE_QUALITY,
        },
    )
    image_base64 = result["data"][0]["b64_json"]
    image_bytes = base64.b64decode(image_base64)
    path = IMAGE_DIR / f"openai-image-{int(time.time())}.png"
    path.write_bytes(image_bytes)
    path.chmod(0o600)
    return path


def generate_self_image(prompt: str = "") -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    width = 640
    height = 640
    now = int(time.time())
    clean_prompt = clean_image_prompt(prompt)
    seed = zlib.crc32(f"{clean_prompt}:{now}".encode()) & 0xFFFFFFFF
    rng = random.Random(seed)
    palettes = [
        ((20, 34, 62), (48, 184, 166), (240, 214, 92), (229, 88, 112)),
        ((26, 24, 38), (122, 207, 112), (250, 246, 194), (181, 95, 255)),
        ((18, 35, 34), (245, 142, 83), (255, 231, 153), (91, 164, 255)),
        ((33, 29, 24), (90, 210, 255), (237, 112, 83), (245, 245, 235)),
        ((12, 28, 48), (255, 196, 87), (65, 190, 255), (236, 94, 148)),
    ]
    bg, accent, highlight, contrast = rng.choice(palettes)
    mode = rng.randrange(4)
    spokes = rng.choice([3, 4, 5, 6, 8, 10])
    ring_center = rng.uniform(0.34, 0.58)
    ring_width = rng.uniform(6.0, 14.0)
    twist = rng.uniform(3.0, 12.0)
    phase = rng.uniform(0, math.tau)
    pixels = bytearray()
    for y in range(height):
        ny = (y / (height - 1)) * 2 - 1
        for x in range(width):
            nx = (x / (width - 1)) * 2 - 1
            radius = math.sqrt(nx * nx + ny * ny)
            angle = math.atan2(ny, nx)
            petal = 0.5 + 0.5 * math.cos(spokes * angle + twist * radius + phase)
            wave = math.sin((12 + mode * 5) * radius + phase) + math.cos((spokes + 2) * angle + radius * twist)
            core = max(0.0, 1.0 - radius)
            ring = max(0.0, 1.0 - abs(radius - ring_center) * ring_width)
            halo = max(0.0, 1.0 - abs(radius - (ring_center + 0.18)) * (ring_width * 0.55))
            if mode == 0:
                mix_a = core * 0.95 + ring * 0.8
                mix_b = petal * core + halo * 0.35
            elif mode == 1:
                mix_a = ring * 1.2 + petal * 0.35
                mix_b = core * 0.8 + halo * 0.5
            elif mode == 2:
                mix_a = petal * (1.0 - min(1.0, radius)) + halo
                mix_b = ring * 0.9 + core * 0.45
            else:
                mix_a = abs(math.sin(angle * spokes + phase)) * core + ring
                mix_b = max(0.0, 1.0 - radius * 0.75) + halo * 0.35

            channels = []
            for i in range(3):
                value = (
                    bg[i] * (1.0 - min(1.0, radius * 0.65))
                    + accent[i] * mix_a
                    + highlight[i] * ring * 0.75
                    + contrast[i] * mix_b * 0.45
                    + 18 * wave
                )
                channels.append(int(max(0, min(255, value))))
            r, g, b = channels
            pixels.extend((r, g, b))
    path = IMAGE_DIR / f"codex-self-{now}-{seed:x}.png"
    write_png(path, width, height, bytes(pixels))
    return path


def wants_self_image(text: str) -> bool:
    return command_name(normalized_command(text)) == "/image"


def wants_topic_creation(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered in {"/newtopic", "/topic", "/create_topic", "/agent"}:
        return True
    if lowered.startswith("/agent "):
        return True
    return (
        "create topic" in lowered
        or "new topic" in lowered
        or "make a topic" in lowered
        or "start a topic" in lowered
    )


def bot_task_prompt(task: str) -> str:
    return (
        "This is an owner-only bot/ecosystem update task for this Telegram Codex bot.\n"
        f"Primary repo: {REPO_ROOT}\n"
        "Relevant ecosystem paths may include ~/.codex/skills and Codex config.\n"
        "Before editing, confirm this checkout is the codexlav repo and create a feature branch from main for the task.\n"
        "Read existing code first. Keep edits scoped. Verify with relevant checks.\n"
        "Before finishing, run scripts/validate_release.sh from the repo root. If it passes, commit on the feature branch, merge back to main, and leave main checked out.\n"
        "Never commit .env, runtime state, uploads, generated files, tokens, chat IDs, user IDs, local absolute home paths, or other private machine data.\n"
        "Do not restart the bot service yourself. If restart is needed, say so in final output; the bot will show a restart button after your output.\n\n"
        f"Owner task:\n{task.strip()}"
    )


def is_bot_update_command(cmd_name: str) -> bool:
    return cmd_name in {"/bot", "/model", "/reason", "/reasoning", "/plan", "/reload", "/clear", "/delete", "/sessions", "/restart", "/topicname"}


def format_uploaded_file_context(file_path: Path) -> str:
    inline_text = downloaded_file_text(file_path)
    if inline_text is not None:
        return (
            f"Attached file: {file_path.name}\n"
            f"Path: {file_path}\n"
            "File content:\n"
            f"```text\n{inline_text}\n```"
        )
    return (
        f"Attached file: {file_path.name}\n"
        f"Path: {file_path}\n"
        "The file is not plain text. Inspect it from the path above."
    )


def topic_name_from_agent(text: str) -> str:
    if text.lower().startswith("/agent"):
        topic_name = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        return topic_name[:128] if topic_name else "Codex"
    topic_name = re.sub(r"^/(newtopic|topic|create_topic)\s*", "", text, flags=re.I).strip()
    return topic_name[:128] if topic_name else "Codex"


def chat_display_name(chat: dict, user: dict) -> str:
    if chat.get("title"):
        return str(chat["title"])
    if chat.get("username"):
        return "@" + str(chat["username"])
    parts = [str(user.get("first_name") or "").strip(), str(user.get("last_name") or "").strip()]
    name = " ".join(part for part in parts if part)
    return name or str(chat.get("id") or "unknown")


def topic_display_name(message: dict, chat_id: int, thread_id: int | None) -> str | None:
    for field in ("forum_topic_created", "forum_topic_edited"):
        topic = message.get(field) or {}
        if topic.get("name"):
            return str(topic["name"])
    reply = message.get("reply_to_message") or {}
    for field in ("forum_topic_created", "forum_topic_edited"):
        topic = reply.get(field) or {}
        if topic.get("name"):
            return str(topic["name"])
    if thread_id is None:
        return "DM" if chat_id > 0 else "General"
    return None


def message_text(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def message_sender_label(message: dict) -> str:
    user = message.get("from") or {}
    if user.get("username"):
        return "@" + str(user["username"])
    parts = [str(user.get("first_name") or "").strip(), str(user.get("last_name") or "").strip()]
    return " ".join(part for part in parts if part) or str(user.get("id") or "unknown")


def extract_single_message_files(message: dict) -> tuple[list[Path], list[str]]:
    photos = message.get("photo") or []
    if photos:
        largest = max(photos, key=lambda item: item.get("file_size", 0))
        return [download_telegram_file(largest["file_id"])], []

    document = message.get("document") or {}
    mime_type = document.get("mime_type") or ""
    file_id = document.get("file_id")
    if mime_type.startswith("image/") and file_id:
        return [download_telegram_file(file_id)], []
    if file_id:
        file_path = download_telegram_file(file_id)
        return [], [format_uploaded_file_context(file_path)]

    return [], []


def extract_message_files(message: dict) -> tuple[list[Path], str | None]:
    messages = message.get("_media_group_messages") or [message]
    image_paths: list[Path] = []
    file_contexts: list[str] = []
    for item in messages:
        item_images, item_contexts = extract_single_message_files(item)
        image_paths.extend(item_images)
        file_contexts.extend(item_contexts)
    return image_paths, "\n\n".join(file_contexts).strip() or None


def reply_reference(message: dict) -> tuple[str | None, list[Path], str | None]:
    reply = message.get("reply_to_message") or {}
    if not reply:
        return None, [], None

    parts = [f"Replied-to message from {message_sender_label(reply)}:"]
    text = message_text(reply)
    if text:
        parts.append(f"```text\n{text}\n```")

    image_paths, file_context = extract_message_files(reply)
    if image_paths:
        listed = "\n".join(f"- {path}" for path in image_paths)
        parts.append(f"Replied-to image paths:\n{listed}")
    if file_context:
        parts.append(file_context)

    if len(parts) == 1:
        parts.append("(no text content)")
    return "\n".join(parts), image_paths, file_context


def prompt_with_reply_context(text: str, reply_context: str | None) -> str:
    if not reply_context:
        return text
    if text.startswith("/"):
        return f"{text}\n\n{reply_context}"
    return f"{reply_context}\n\nUser message:\n{text}"


def media_group_key(message: dict) -> str:
    chat = message.get("chat") or {}
    return f"{chat.get('id')}:{message.get('media_group_id')}"


def merge_media_group_messages(messages: list[dict]) -> dict:
    messages = sorted(messages, key=lambda item: int(item.get("message_id") or 0))
    merged = dict(messages[0])
    text = next((message_text(item) for item in messages if message_text(item)), "")
    if text:
        merged["caption"] = text
        merged.pop("text", None)
    merged["_media_group_messages"] = messages
    return merged


def flush_media_group(key: str) -> None:
    with media_group_lock:
        entry = media_group_buffers.pop(key, None)
    if not entry:
        return
    messages = entry.get("messages") or []
    if not messages:
        return
    handle_message(merge_media_group_messages(messages))


def handle_media_group_message(message: dict) -> None:
    key = media_group_key(message)
    with media_group_lock:
        entry = media_group_buffers.get(key)
        if entry is None:
            entry = {"messages": [], "timer": None}
            media_group_buffers[key] = entry
        timer = entry.get("timer")
        if timer is not None:
            timer.cancel()
        entry["messages"].append(message)
        timer = threading.Timer(MEDIA_GROUP_DELAY_SECONDS, flush_media_group, args=(key,))
        timer.daemon = True
        entry["timer"] = timer
        timer.start()


def handle_message(message: dict) -> None:
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")
    user_id = user.get("id")
    thread_id = message_thread_id(message)
    if chat_id is not None and thread_id is not None:
        topic_name = topic_display_name(message, chat_id, thread_id)
        if topic_name:
            set_topic_metadata(chat_id, thread_id, chat_name=chat_display_name(chat, user), topic_name=topic_name)
    if chat_id is not None and message.get("forum_topic_deleted") is not None:
        entry = delete_topic_state(chat_id, thread_id)
        try:
            archive_topic_session(entry)
        except Exception as exc:
            log(f"topic session archive failed chat_id={chat_id} thread_id={thread_id} error={exc}")
        log(f"topic deleted chat_id={chat_id} thread_id={thread_id}; state cleared")
        return
    text = message_text(message)
    if chat_id is None or user_id is None:
        return
    log(
        f"received message chat_id={chat_id} thread_id={thread_id} "
        f"is_topic={message.get('is_topic_message')} user_id={user_id} text={text[:80]!r}"
    )
    command_text = normalized_command(text)
    cmd_name = command_name(command_text)

    if cmd_name == "/id":
        send_message(chat_id, f"Your Telegram user id is: {user_id}")
        return

    if not ALLOWED_IDS:
        send_message(
            chat_id,
            "Bot is not configured yet. Set TELEGRAM_ALLOWED_USER_IDS to your user id. Send /id to see it.",
        )
        return

    if not is_allowed(user_id) or not is_allowed_chat(chat_id):
        log(f"ignored unauthorized message chat_id={chat_id} user_id={user_id}")
        return

    set_topic_metadata(
        chat_id,
        thread_id,
        chat_name=chat_display_name(chat, user),
        topic_name=topic_display_name(message, chat_id, thread_id),
    )

    if is_bot_update_command(cmd_name) and not is_owner(user_id):
        send_message(chat_id, "Bot update commands are owner-only.", thread_id)
        return
    if cmd_name == "/restart" and chat_id < 0:
        send_message(chat_id, "/restart works only in private chat with owner.", thread_id)
        return

    if cmd_name in {"/start", "/help"}:
        restart_help = "/restart shows the restart button.\n" if chat_id > 0 and is_owner(user_id) else ""
        send_message(
            chat_id,
            "Send a message to run it through Codex on this machine.\n"
            "Send a photo with an optional caption to analyze it.\n"
            "Send a file to inspect text files or pass non-image files to Codex.\n"
            "/image generates an image through Codex built-in image generation.\n"
            "/lastimage sends the newest built-in image_gen output.\n"
            "/images lists recent built-in image_gen outputs.\n"
            "/agent creates a new topic/session from general.\n"
            "/bot <task> runs an owner-only bot/ecosystem update task.\n"
            "/delete deletes current topic thread.\n"
            "/model chooses the Codex model.\n"
            "/reason chooses reasoning effort.\n"
            "/recap gives a one-sentence session summary.\n"
            "/sessions shows sessions and agents.\n"
            "/topicname sets current topic display name.\n"
            f"{restart_help}"
            "/handoff writes a markdown handoff document.\n"
            "/status shows configuration.\n"
            "/id shows your Telegram user id.",
        )
        return

    if cmd_name == "/bot":
        parts = command_text.split(None, 1)
        if len(parts) == 1:
            send_message(chat_id, "Usage: /bot <bot or ecosystem update task>", thread_id)
            return
        task = parts[1].strip()
        enqueue_work(
            {
                "kind": "bot_update",
                "chat_id": chat_id,
                "thread_id": thread_id,
                "text": style_prompt(bot_task_prompt(task)),
                "image_paths": [],
            },
            status_text="Updating bot...",
        )
        depth = current_queue_depth()
        log(f"queued bot-update chat_id={chat_id} depth={depth} prompt_chars={len(task)}")
        return

    if cmd_name == "/model":
        send_model_menu(chat_id, thread_id)
        return

    if cmd_name in {"/reason", "/reasoning"}:
        send_reasoning_menu(chat_id, thread_id)
        return

    if cmd_name == "/sessions":
        send_sessions_recap(chat_id, thread_id)
        return

    if cmd_name == "/topicname":
        parts = command_text.split(None, 1)
        if len(parts) == 1 or not parts[1].strip():
            send_message(chat_id, "Usage: /topicname <display name>", thread_id)
            return
        set_topic_name(chat_id, thread_id, parts[1].strip())
        send_message(chat_id, f"Topic name set: {parts[1].strip()[:128]}", thread_id)
        return

    if cmd_name == "/restart":
        send_restart_button(chat_id, thread_id)
        return

    if cmd_name == "/lastimage":
        send_latest_generated_image(chat_id, thread_id)
        return

    if cmd_name == "/images":
        send_generated_image_menu(chat_id, thread_id)
        return

    if cmd_name == "/plan":
        set_topic_mode(chat_id, thread_id, "plan")
        send_message(chat_id, "Plan mode set for this thread.", thread_id)
        return

    if cmd_name == "/reload":
        clear_topic_session(chat_id, thread_id)
        send_message(chat_id, "Session cleared. Next prompt starts fresh.", thread_id)
        return

    if cmd_name == "/clear":
        clear_topic_session(chat_id, thread_id)
        set_topic_mode(chat_id, thread_id, "chat")
        send_message(chat_id, "Topic session cleared.", thread_id)
        return

    if cmd_name == "/delete":
        if chat_id >= 0 or thread_id is None:
            send_message(chat_id, "/delete works only inside a topic thread.", thread_id)
            return
        entry = delete_topic_state(chat_id, thread_id)
        try:
            archive_result = archive_topic_session(entry)
        except Exception as exc:
            archive_result = f"Codex archive failed: {exc}"
        try:
            archive_line = f"\n{archive_result}" if archive_result else ""
            send_message(chat_id, f"Deleting topic, clearing state, archiving Codex session...{archive_line}", thread_id=thread_id)
            delete_forum_topic(chat_id, thread_id)
        except Exception as exc:
            send_message(chat_id, f"Topic delete failed: {exc}", thread_id)
        return

    if cmd_name == "/status":
        session = CODEX_SESSION_ID or "latest recorded Codex session"
        topic_session = get_topic_session(chat_id, thread_id)
        topic_mode = get_topic_mode(chat_id, thread_id)
        usage_lines = codex_rate_limit_status()
        send_message(
            chat_id,
            "```text\n"
            f"Codex cwd: {CODEX_CWD}\n"
            f"Codex session: {session}\n"
            f"Allowed chats: {', '.join(sorted(ALLOWED_CHAT_IDS)) or 'DM only'}\n"
            f"Topic key: {topic_key(chat_id, thread_id)}\n"
            f"Topic mode: {topic_mode}\n"
            f"Topic session: {topic_session or 'none'}\n"
            f"Codex model: {model_label(chat_id=chat_id, thread_id=thread_id)}\n"
            f"Codex reasoning: {reasoning_label(chat_id=chat_id, thread_id=thread_id)}\n"
            f"Codex yolo: {CODEX_YOLO}\n"
            f"Queue depth: {current_queue_depth()}\n"
            f"{usage_lines}"
            f"Session file: {codex_session_file(topic_session or None) or 'not found'}\n"
            "```",
            thread_id,
        )
        return

    if cmd_name == "/recap":
        session_id = get_topic_session(chat_id, thread_id)
        if not session_id:
            send_message(chat_id, "No topic Codex session recorded yet.", thread_id)
            send_sessions_button(chat_id, thread_id)
            return
        prompt = recap_prompt()
        enqueue_work(
            {"kind": "recap", "chat_id": chat_id, "thread_id": thread_id, "text": style_prompt(prompt), "image_paths": []},
            status_text="Recapping...",
        )
        log(f"queued recap chat_id={chat_id} thread_id={thread_id} depth={current_queue_depth()}")
        return

    if cmd_name == "/handoff":
        session_id = get_topic_session(chat_id, thread_id)
        if not session_id:
            send_message(chat_id, "No topic Codex session recorded yet.", thread_id)
            return
        prompt = (
            "$handoff\n"
            "Create a concise Markdown handoff document for the current Codex session. "
            "Use the required handoff sections. Include exact paths, current status, open work, and next steps. "
            "Do not include secrets."
        )
        work_queue.put({"kind": "handoff", "chat_id": chat_id, "thread_id": thread_id, "text": style_prompt(prompt), "image_paths": []})
        log(f"queued handoff chat_id={chat_id} thread_id={thread_id} depth={current_queue_depth()}")
        return

    if chat_id < 0 and wants_topic_creation(text):
        topic_name = topic_name_from_agent(text)
        try:
            new_thread_id = create_forum_topic(chat_id, topic_name)
            set_topic_metadata(chat_id, new_thread_id, chat_name=chat_display_name(chat, user), topic_name=topic_name)
            send_message(
                chat_id,
                f"Created topic: {topic_name}\nUse that topic for Codex work.",
                thread_id=new_thread_id,
            )
        except Exception as exc:
            send_message(chat_id, f"Topic creation failed: {exc}")
        return

    if chat_id < 0 and thread_id is None:
        if text and not text.startswith("/"):
            send_message(chat_id, "Use a topic for Codex work. Ask me here to create one.", thread_id=None)
        return

    image_paths, file_context = extract_message_files(message)
    reply_context, reply_image_paths, _reply_file_context = reply_reference(message)
    if reply_image_paths:
        image_paths.extend(reply_image_paths)
    context_parts = [part for part in (file_context, reply_context) if part]
    combined_context = "\n\n".join(context_parts).strip()
    if wants_self_image(text):
        prompt_text = prompt_with_reply_context(text, reply_context)
        work_queue.put(
            {
                "kind": "imagegen",
                "chat_id": chat_id,
                "thread_id": thread_id,
                "text": prompt_text,
                "caption": clean_image_prompt(text),
                "image_paths": image_paths,
            }
        )
        depth = current_queue_depth()
        log(f"queued imagegen chat_id={chat_id} depth={depth} images={len(image_paths)}")
        return

    if image_paths:
        prompt = text or "Analyze this image. Describe what is visible and call out any important details."
        prompt = prompt_with_reply_context(prompt, combined_context)
        item = {"chat_id": chat_id, "thread_id": thread_id, "text": style_prompt(prompt), "image_paths": image_paths}
        if text.startswith("/"):
            work_queue.put(item)
        else:
            enqueue_work(item)
        depth = current_queue_depth()
        log(f"queued image-analysis chat_id={chat_id} depth={depth} images={len(image_paths)}")
        return

    if file_context:
        prompt = text or "Inspect the attached file and summarize the useful parts."
        prompt = prompt_with_reply_context(prompt, combined_context)
        item = {"chat_id": chat_id, "thread_id": thread_id, "text": style_prompt(prompt), "image_paths": []}
        if text.startswith("/"):
            work_queue.put(item)
        else:
            enqueue_work(item)
        depth = current_queue_depth()
        log(f"queued file-analysis chat_id={chat_id} depth={depth}")
        return

    if not text and not reply_context:
        send_message(chat_id, "Send text, an image, or a file.", thread_id)
        return

    if reply_context and not text:
        text = "Use the replied-to message as context."
    topic_mode = get_topic_mode(chat_id, thread_id)
    if topic_mode == "plan":
        text = f"Create a concise execution plan for this thread. Do not execute it yet.\n\nUser request:\n{text}"
    prompt = prompt_with_reply_context(text, reply_context)
    item = {"chat_id": chat_id, "thread_id": thread_id, "text": style_prompt(prompt), "image_paths": []}
    if text.startswith("/"):
        work_queue.put(item)
    else:
        enqueue_work(item)
    depth = current_queue_depth()
    log(f"queued codex chat_id={chat_id} depth={depth} prompt_chars={len(text)}")


def handle_callback_query(callback_query: dict) -> None:
    user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    user_id = user.get("id")
    chat_id = chat.get("id")
    callback_id = callback_query.get("id")
    data = callback_query.get("data") or ""
    log(f"received callback chat_id={chat_id} user_id={user_id} data={data!r}")

    if callback_id is None or user_id is None or chat_id is None:
        return
    if not is_allowed(user_id) or not is_allowed_chat(chat_id):
        log(f"ignored unauthorized callback chat_id={chat_id} user_id={user_id}")
        return
    if (
        data.startswith("model:")
        or data.startswith("reasoning:")
        or data.startswith("session_recap:")
        or data in {"model_menu:reasoning", "reasoning_menu:model"}
        or data in {"bot_restart", "sessions:recap"}
    ) and not is_owner(user_id):
        answer_callback(callback_id, "Owner only.")
        return
    thread_id = message_thread_id(message)
    if data == "bot_restart":
        if chat_id < 0:
            answer_callback(callback_id, "Restart only in owner private chat.")
            send_restart_button(chat_id, thread_id)
            return
        answer_callback(callback_id, "Restarting bot.")
        message_id = message.get("message_id")
        if message_id is not None:
            try:
                request_json(
                    "editMessageReplyMarkup",
                    {
                        "chat_id": str(chat_id),
                        "message_id": str(message_id),
                        "reply_markup": json.dumps({"inline_keyboard": []}),
                    },
                )
            except Exception as exc:
                log(f"restart button disable failed chat_id={chat_id} message_id={message_id} error={exc}")
        save_restart_notification(chat_id, thread_id)
        send_message(chat_id, "Restarting bot service...", thread_id)
        subprocess.Popen(
            ["systemctl", "--user", "restart", "telegram-codex-bot.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=CODEX_CWD,
        )
        return
    if data == "sessions:recap":
        answer_callback(callback_id, "Sessions.")
        send_sessions_recap(chat_id, thread_id)
        return
    if data.startswith("session_recap:"):
        try:
            index = int(data.removeprefix("session_recap:"))
            key, entry = session_entries()[index]
            target_chat_id, target_thread_id = parse_topic_key(key)
        except (ValueError, IndexError):
            answer_callback(callback_id, "Session not found.")
            return
        session_id = str(entry.get("session_id", "")).strip()
        if not session_id:
            answer_callback(callback_id, "No session id.")
            return
        answer_callback(callback_id, "Recapping session.")
        enqueue_work(
            {
                "kind": "session_recap",
                "chat_id": chat_id,
                "thread_id": thread_id,
                "target_chat_id": target_chat_id,
                "target_thread_id": target_thread_id,
                "target_session_id": session_id,
                "text": style_prompt(recap_prompt()),
                "image_paths": [],
            },
            status_text="Recapping selected session...",
        )
        return
    if data == "model_menu:reasoning":
        answer_callback(callback_id, "Reasoning.")
        send_reasoning_menu(chat_id, thread_id)
        return
    if data == "reasoning_menu:model":
        answer_callback(callback_id, "Models.")
        send_model_menu(chat_id, thread_id)
        return
    if not data.startswith("model:"):
        if data.startswith("send_builtin_image:"):
            try:
                index = int(data.removeprefix("send_builtin_image:"))
                image_path = generated_image_files()[index]
            except (ValueError, IndexError):
                answer_callback(callback_id, "Image no longer available.")
                return
            answer_callback(callback_id, "Sending image.")
            send_photo(chat_id, image_path, f"Built-in image_gen output: {image_path.name}", thread_id)
            return

        if not data.startswith("reasoning:"):
            answer_callback(callback_id)
            return
        option = data.removeprefix("reasoning:")
        if option != "default" and option not in REASONING_OPTIONS:
            answer_callback(callback_id, "Unknown reasoning option.")
            return
        set_current_reasoning(option, chat_id, thread_id)
        answer_callback(callback_id, f"Reasoning set to {reasoning_label(chat_id=chat_id, thread_id=thread_id)}.")
        send_model_menu(chat_id, thread_id)
        return

    option = data.removeprefix("model:")
    if option not in CODEX_MODEL_OPTIONS:
        answer_callback(callback_id, "Unknown model option.")
        return

    set_current_model(option, chat_id, thread_id)
    answer_callback(callback_id, f"Model set to {model_label(chat_id=chat_id, thread_id=thread_id)}.")
    send_model_menu(chat_id, thread_id)


def worker() -> None:
    while True:
        item = work_queue.get()
        chat_id = item["chat_id"]
        thread_id = item.get("thread_id")
        status_message_id = item.get("status_message_id")
        prompt = item["text"]
        image_paths = item.get("image_paths") or []
        selected_model = current_model(chat_id, thread_id)
        selected_reasoning = current_reasoning(chat_id, thread_id)
        try:
            if item.get("kind") == "imagegen":
                log(f"worker start imagegen chat_id={chat_id}")
                send_message(chat_id, "Generating image...", thread_id)
                image_path = generate_builtin_codex_image(
                    prompt,
                    chat_id,
                    thread_id,
                    image_paths=image_paths,
                    selected_model=selected_model,
                    selected_reasoning=selected_reasoning,
                )
                caption = item.get("caption") or clean_image_prompt(prompt)
                send_photo(chat_id, image_path, f"Generated with Codex image_gen: {caption}", thread_id)
            elif item.get("kind") in {"recap", "handoff"}:
                kind = item["kind"]
                log(f"worker start {kind} chat_id={chat_id}")
                session_id = get_topic_session(chat_id, thread_id)
                if not session_id:
                    send_message(chat_id, "No topic Codex session recorded yet.", thread_id)
                    continue
                output = run_codex_streaming(
                    prompt,
                    chat_id,
                    thread_id,
                    image_paths,
                    session_id=session_id,
                    resume=True,
                    status_message_id=status_message_id,
                    selected_model=selected_model,
                    selected_reasoning=selected_reasoning,
                )
                if kind == "recap":
                    recap_text = " ".join(output.split())
                    set_topic_recap(chat_id, thread_id, recap_text)
                    finish_text_response(chat_id, thread_id, status_message_id, recap_text)
                    send_sessions_button(chat_id, thread_id)
                else:
                    handoff_path = write_handoff_file(chat_id, thread_id, output)
                    delete_message(chat_id, status_message_id)
                    send_document(chat_id, handoff_path, f"Handoff: {handoff_path.name}", thread_id)
                    send_message(chat_id, f"Handoff written: {handoff_path}", thread_id)
            elif item.get("kind") == "session_recap":
                log(f"worker start session_recap chat_id={chat_id}")
                target_chat_id = int(item["target_chat_id"])
                target_thread_id = item.get("target_thread_id")
                target_session_id = str(item["target_session_id"])
                target_model = current_model(target_chat_id, target_thread_id)
                target_reasoning = current_reasoning(target_chat_id, target_thread_id)
                output = run_codex_streaming(
                    prompt,
                    chat_id,
                    thread_id,
                    image_paths,
                    session_id=target_session_id,
                    resume=True,
                    status_message_id=status_message_id,
                    selected_model=target_model,
                    selected_reasoning=target_reasoning,
                )
                recap_text = " ".join(output.split())
                set_topic_recap(target_chat_id, target_thread_id, recap_text)
                finish_text_response(chat_id, thread_id, status_message_id, recap_text)
                send_sessions_recap(chat_id, thread_id)
            else:
                log(f"worker start codex chat_id={chat_id} images={len(image_paths)}")
                session_id = get_topic_session(chat_id, thread_id)
                if session_id:
                    output = run_codex_streaming(
                        prompt,
                        chat_id,
                        thread_id,
                        image_paths,
                        session_id=session_id,
                        resume=True,
                        status_message_id=status_message_id,
                        selected_model=selected_model,
                        selected_reasoning=selected_reasoning,
                    )
                else:
                    session_id, output = start_codex_session(
                        prompt,
                        image_paths,
                        selected_model=selected_model,
                        selected_reasoning=selected_reasoning,
                    )
                    if session_id:
                        set_topic_session(chat_id, thread_id, session_id)
                clean_output, upload_requests = parse_upload_blocks(output)
                if clean_output:
                    finish_text_response(chat_id, thread_id, status_message_id, clean_output)
                else:
                    delete_message(chat_id, status_message_id)
                execute_upload_requests(chat_id, thread_id, upload_requests)
                artifact_path = extract_artifact_path(clean_output)
                if artifact_path:
                    send_artifact(chat_id, artifact_path, thread_id)
                if item.get("kind") == "bot_update":
                    send_restart_button(chat_id, thread_id)
        except subprocess.TimeoutExpired:
            finish_text_response(chat_id, thread_id, status_message_id, f"Codex timed out after {CODEX_TIMEOUT_SECONDS} seconds.")
        except Exception as exc:
            finish_text_response(chat_id, thread_id, status_message_id, f"Bot error: {exc}")
        finally:
            work_queue.task_done()


def start_worker() -> threading.Thread:
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    log("worker started")
    return thread


def main() -> None:
    if not TOKEN:
        die("TELEGRAM_BOT_TOKEN is required.")
    if not os.path.isdir(CODEX_CWD):
        die(f"CODEX_CWD does not exist or is not a directory: {CODEX_CWD}")
    load_state()
    load_topic_state()
    set_bot_commands()
    send_restart_ready_notification()

    worker_thread = start_worker()
    offset = load_update_offset()
    log("telegram-codex-bot started")
    while True:
        try:
            if not worker_thread.is_alive():
                log("worker stopped unexpectedly; restarting")
                worker_thread = start_worker()
            params = {"timeout": str(POLL_TIMEOUT_SECONDS)}
            if offset is not None:
                params["offset"] = str(offset)
            updates = request_json("getUpdates", params).get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                save_update_offset(offset)
                callback_query = update.get("callback_query")
                if callback_query:
                    handle_callback_query(callback_query)
                message = update.get("message") or update.get("edited_message")
                if message:
                    if message.get("media_group_id"):
                        handle_media_group_message(message)
                    else:
                        handle_message(message)
        except Exception as exc:
            print(f"poll error: {exc}", file=sys.stderr, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
