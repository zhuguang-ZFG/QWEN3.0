"""LiMa channel branding — 动力巢科技对外展示（微信访客）。"""

from __future__ import annotations

import os

COMPANY_NAME = os.environ.get("LIMA_COMPANY_NAME", "深圳市动力巢科技有限公司")
BRAND_SITE = os.environ.get("LIMA_BRAND_SITE", "https://www.donglilicao.com")
PRODUCT_SITE = os.environ.get("LIMA_PRODUCT_SITE", "https://chat.donglicao.com")
BRAND_TAGLINE = os.environ.get(
    "LIMA_BRAND_TAGLINE",
    "LiMa 智能路由 · 编码与硬件助手 · ESP32 可执行",
)


def brand_footer(*, short: bool = False) -> str:
    if short:
        return f"—— {COMPANY_NAME}\n{BRAND_SITE}"
    return (
        f"—— {COMPANY_NAME}\n"
        f"{BRAND_TAGLINE}\n"
        f"官网 {BRAND_SITE.replace('https://', '')} · 在线体验 {PRODUCT_SITE.replace('https://', '')}"
    )


def company_pitch() -> str:
    return (
        f"【{COMPANY_NAME}】\n"
        f"{BRAND_TAGLINE}\n\n"
        "我们做什么：\n"
        "· LiMa：多后端智能路由，为 Cursor/IDE 与访客提供稳定 AI 能力\n"
        "· 微信助手：聊天、语音、文件/图片分析、实用工具（/menu）\n"
        "· ESP32 / 设备网关：路径规划、真机执行与可观测闭环\n\n"
        f"官网：{BRAND_SITE}\n"
        f"在线体验：{PRODUCT_SITE}\n"
        "合作与定制开发请联系管理员（微信主人账号 /bind 后可看 /简报）。"
    )


def maybe_brand_footer(text: str, *, enabled: bool | None = None) -> str:
    if not (text or "").strip():
        return text
    if enabled is None:
        enabled = os.environ.get("LIMA_CHANNEL_BRAND_FOOTER", "1") == "1"
    if not enabled:
        return text
    if "donglilicao.com" in text or "donglicao.com" in text or "动力巢" in text:
        return text
    if len(text) > 3200:
        return text
    return f"{text.rstrip()}\n\n{brand_footer(short=True)}"
