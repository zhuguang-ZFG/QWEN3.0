"""Per-user daily quotas for channel guest/owner tools."""

from __future__ import annotations

import os
import time
from typing import Optional

from channel_gateway.models import BindingRole

# guest daily limits (owner uses LIMA_CHANNEL_OWNER_TOOL_MULT or per-tool override)
_GUEST_LIMITS: dict[str, int] = {
    "wiki": 15,
    "weather": 10,
    "search": 8,
    "read_url": 3,
    "news": 5,
    "translate": 10,
    "exchange": 10,
    "time": 30,
    "hot": 5,
    "ip": 5,
    "calc": 30,
    "holiday": 10,
    "stock": 8,
    "earthquake": 5,
    "dict": 10,
    "whois": 5,
    "qr": 10,
    "geocode": 8,
    "randomuser": 5,
    "ssl": 8,
    "regex": 20,
    "image": 8,
    "uuid": 20,
}

_OWNER_MULT = float(os.environ.get("LIMA_CHANNEL_OWNER_TOOL_MULT", "3"))


def tools_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_TOOLS", "0") == "1"


def tool_limit(tool: str, role: str) -> int:
    base = _GUEST_LIMITS.get(tool, 0)
    if base <= 0:
        return 0
    if role == BindingRole.OWNER:
        return max(base, int(base * _OWNER_MULT))
    return base


def utc_day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def quota_exceeded_message(tool: str, limit: int) -> str:
    labels = {
        "wiki": "百科",
        "weather": "天气",
        "search": "搜索",
        "read_url": "读链接",
        "news": "新闻",
        "translate": "翻译",
        "exchange": "汇率",
        "time": "时间",
        "hot": "热搜",
        "ip": "IP 查询",
        "calc": "计算器",
        "holiday": "黄历",
        "stock": "股票",
        "earthquake": "地震",
        "dict": "词典",
        "whois": "WHOIS",
        "qr": "二维码",
        "geocode": "地理编码",
        "randomuser": "假数据",
        "ssl": "SSL 检查",
        "regex": "正则测试",
        "image": "图片",
        "uuid": "UUID",
    }
    name = labels.get(tool, tool)
    return (
        f"今日{name}次数已用完（{limit} 次/天）。明天再试，或发送 /help。"
    )
