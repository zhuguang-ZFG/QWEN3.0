"""Greeting detection and first-contact replies for channel guests."""

from __future__ import annotations

import re

from channel_gateway.branding import maybe_brand_footer

_GREETING_RE = re.compile(
    r"^(你好|您好|嗨|哈喽|在吗|有人吗|hi|hello|hey)[\s!！?？。.~、，,]*$",
    re.IGNORECASE,
)


def is_greeting(text: str) -> bool:
    return bool(_GREETING_RE.match((text or "").strip()))


def greeting_reply() -> str:
    return maybe_brand_footer(
        "你好，我是 LiMa 微信助手（动力巢科技）。\n"
        "可打字、发语音、发图片/文件；发「菜单」或用 /menu。\n"
        "发「官网」或 /公司 了解我们，「帮助」或 /help 看命令。"
    )
