"""Weixin iLink bot invite copy — cannot forward as normal WeChat contact card."""

from __future__ import annotations

import os

from channel_gateway.branding import BRAND_SITE, COMPANY_NAME


def invite_text(*, bot_id: str = "", share_url: str = "") -> str:
    bid = (bot_id or os.environ.get("LIMA_WEIXIN_BOT_ID", "")).strip()
    if not bid:
        try:
            import json
            from pathlib import Path

            home = Path.home() / ".hermes" / "weixin" / "accounts"
            for p in sorted(home.glob("*.json")):
                if "context" not in p.name and "sync" not in p.name:
                    bid = p.stem
                    break
        except Exception:
            pass
    url = (share_url or os.environ.get("LIMA_WEIXIN_SHARE_URL", "")).strip()
    lines = [
        "【如何添加 LiMa 微信助手】",
        "",
        "这是微信 iLink 机器人账号，不是普通微信号，",
        "不能像「推荐名片」那样转发给好友。",
        "",
        "请让朋友任选一种方式：",
        "1. 微信扫一扫：打开管理员提供的加好友二维码/链接",
        "2. 在微信里搜索并添加机器人（若平台开放搜索）",
        "3. 添加后直接发消息，无需绑定码",
        "",
    ]
    if bid:
        lines.append(f"机器人 ID：{bid}")
    if url:
        lines.append(f"扫码链接：{url}")
    lines.extend([
        "",
        "添加后可直接聊天，或发：帮助 / 菜单 / 公司",
        f"官网：{BRAND_SITE.replace('https://', '')}",
        "",
        f"—— {COMPANY_NAME} · LiMa 微信助手",
    ])
    return "\n".join(lines)
