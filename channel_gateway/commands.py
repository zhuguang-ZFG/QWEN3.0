"""Channel Gateway command parser.

Parses WeChat-style text commands into structured intent + args.

V1 guest commands: /bind /chat /code /draw /demo /about /reset /pause /resume /unbind /help
V2 owner-only: /code-task /device /status /artifact /memory
"""

import os
import re
from channel_gateway.models import CommandResult

MAX_TEXT_LENGTH = int(os.environ.get("LIMA_CHANNEL_MAX_TEXT", "4000"))

_GUEST_COMMANDS = {
    "bind": "bind",
    "chat": "chat",
    "code": "code",
    "draw": "draw",
    "demo": "demo",
    "about": "about",
    "reset": "reset",
    "pause": "pause",
    "resume": "resume",
    "unbind": "unbind",
    "help": "help",
}

_OWNER_COMMANDS = {
    "code-task": "code_task",
    "device": "device",
    "status": "status",
    "artifact": "artifact",
    "memory": "memory",
}

_ALL_COMMANDS = {**_GUEST_COMMANDS, **_OWNER_COMMANDS}

_COMMAND_RE = re.compile(r"^\s*/(\S+)\s*(.*)", re.DOTALL)


def parse_command(text: str) -> CommandResult:
    raw = text.strip()
    if len(raw) > MAX_TEXT_LENGTH:
        raw = raw[:MAX_TEXT_LENGTH]
    if not raw:
        return CommandResult(intent="unknown", args="", raw_text="")

    m = _COMMAND_RE.match(raw)
    if m:
        cmd = m.group(1).lower()
        args = m.group(2).strip()
        intent = _ALL_COMMANDS.get(cmd, "unknown")
        if intent == "unknown":
            return CommandResult(intent="unknown", args="", raw_text=raw)
        return CommandResult(intent=intent, args=args, raw_text=raw)

    # Plain text -> chat
    return CommandResult(intent="chat", args=raw, raw_text=raw)


def is_owner_only(intent: str) -> bool:
    return intent in _OWNER_COMMANDS.values()
