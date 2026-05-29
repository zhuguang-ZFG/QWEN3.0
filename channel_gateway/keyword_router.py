"""Map plain Chinese keywords to slash commands (WeChat guest UX)."""

from __future__ import annotations

import re

from channel_gateway.nl_tool_router import match_nl_tool

_EXACT = {
    "菜单": "/menu",
    "帮助": "/help",
    "使用说明": "/help",
    "官网": "/公司",
    "公司": "/公司",
    "品牌": "/公司",
    "演示": "/demo",
    "体验": "/demo",
    "语音": "/语音",
    "文件": "/文件",
    "关于": "/about",
    "关于我们": "/about",
    "邀请": "/邀请",
    "加好友": "/邀请",
    "语音回复": "/语音回复",
}

_PREFIX = (
    ("天气 ", "/天气 "),
    ("百科 ", "/百科 "),
    ("算 ", "/算 "),
    ("计算 ", "/算 "),
)


def normalize_guest_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return raw
    compact = re.sub(r"[\s!！?？。.~、，,]+$", "", raw)
    if compact in _EXACT:
        return _EXACT[compact]
    low = compact.lower()
    if low in ("help", "menu"):
        return f"/{low}"
    for prefix, cmd in _PREFIX:
        if compact.startswith(prefix):
            return cmd + compact[len(prefix):]
    nl = match_nl_tool(compact)
    if nl:
        return nl
    return raw
