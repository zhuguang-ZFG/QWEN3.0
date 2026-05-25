"""Weixin guest onboarding — WCF 小号 / 网页 / iLink 限制说明."""

from __future__ import annotations

import os

from channel_gateway.branding import BRAND_SITE, COMPANY_NAME, PRODUCT_SITE


def _resolve_bot_id(bot_id: str = "") -> str:
    bid = (bot_id or os.environ.get("LIMA_WEIXIN_BOT_ID", "") or "").strip()
    if bid:
        return bid
    bid = os.environ.get("WEIXIN_ACCOUNT_ID", "").strip()
    if bid:
        return bid
    try:
        from pathlib import Path

        home = Path.home() / ".hermes" / "weixin" / "accounts"
        for p in sorted(home.glob("*.json")):
            if "context" not in p.name and "sync" not in p.name:
                return p.stem
    except Exception:
        pass
    return ""


def invite_text(*, bot_id: str = "", share_url: str = "") -> str:
    """Guest paths: add LiMa 小号 WeChat friend (WCF) or use web; not iLink liteapp."""
    del share_url
    bid = _resolve_bot_id(bot_id)
    web = PRODUCT_SITE
    wx_id = os.environ.get("LIMA_WECHAT_PUBLIC_ID", "").strip()
    lines = [
        "【LiMa 微信访客说明 — 请转发给朋友】",
        "",
        "推荐（微信里像加客服一样用）：",
        "• 添加 LiMa 专用微信小号为好友，直接私聊发「你好」或「/menu」。",
    ]
    if wx_id:
        lines.append(f"  微信号：{wx_id}")
    else:
        lines.append("  （微信号由管理员私信提供，见 docs/WECHAT_WCF_XIAOHAO.md）")
    lines.extend([
        "• 无需 ClawBot 插件、无需扫机器人二维码。",
        "",
        "也可浏览器使用（无需加好友）：",
        f"• {web}",
        "",
        "请勿使用：",
        "• /邀请 里的 liteapp 加机器人链接（访客消息进不了 LiMa，已实测）。",
        "• 管理员个人 ClawBot 机器人（仅管理员本人可用）。",
        "",
        "管理员运维：",
        "• 小号需 Windows PC 微信 + WCF 桥常开，见 docs/WECHAT_WCF_XIAOHAO.md",
    ])
    if bid:
        lines.append(f"• iLink 机器人（仅管理员）：{bid}")
    lines.extend([
        "",
        f"官网：{BRAND_SITE}",
        "",
        f"—— {COMPANY_NAME} · LiMa",
    ])
    return "\n".join(lines)
