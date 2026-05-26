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
    "menu": "menu",
    "公司": "company",
    "品牌": "company",
    "aboutus": "company",
    "语音": "voice_help",
    "文件": "file_help",
    "邀请": "invite",
    "invite": "invite",
    "加好友": "invite",
    "语音回复": "voice_reply",
    # Public tools (LIMA_CHANNEL_TOOLS=1)
    "百科": "wiki",
    "wiki": "wiki",
    "baike": "wiki",
    "定义": "wiki",
    "天气": "weather",
    "weather": "weather",
    "搜": "search",
    "search": "search",
    "读": "read_url",
    "url": "read_url",
    "read": "read_url",
    "新闻": "news",
    "news": "news",
    "翻译": "translate",
    "translate": "translate",
    "汇率": "exchange",
    "exchange": "exchange",
    "时间": "time",
    "time": "time",
    "热搜": "hot",
    "hot": "hot",
    "ip": "ip",
    "算": "calc",
    "calc": "calc",
    "黄历": "holiday",
    "holiday": "holiday",
    "股票": "stock",
    "stock": "stock",
    "地震": "earthquake",
    "earthquake": "earthquake",
    "词典": "dict",
    "dict": "dict",
    "dictionary": "dict",
    "whois": "whois",
    "二维码": "qr",
    "qr": "qr",
    "地理": "geocode",
    "geocode": "geocode",
    "假数据": "randomuser",
    "randomuser": "randomuser",
    "random": "randomuser",
    "fake": "randomuser",
    "ssl": "ssl",
    "正则": "regex",
    "regex": "regex",
    "图片": "image",
    "image": "image",
}

_OWNER_COMMANDS = {
    "code-task": "code_task",
    "device": "device",
    "status": "status",
    "artifact": "artifact",
    "memory": "memory",
    "简报": "digest",
    "digest": "digest",
    "github": "github",
    "gh": "github",
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
