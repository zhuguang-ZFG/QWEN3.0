"""Weixin guest onboarding — honest limits for iLink / ClawBot."""

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
    """Tell guests the real path; do not promise WeChat add-friend via /invite link."""
    del share_url
    bid = _resolve_bot_id(bot_id)
    web = PRODUCT_SITE
    lines = [
        "【LiMa 微信访客说明 — 请转发给朋友】",
        "",
        "重要（已用服务器日志核实）：",
        "• 本 VPS 上的 LiMa 机器人目前只收到「管理员微信」的消息，",
        "  好友扫 /邀请 里的 liteapp 链接后，消息不会进 LiMa，所以不会回复。",
        "• 原因：微信 ClawBot / iLink 目前是「一个微信号绑定一个后端实例」，",
        "  没有「分享同一个机器人给多人加好友」的公开能力（不能搜 ID、不能转发名片）。",
        "",
        "请朋友这样用 LiMa（推荐）：",
        f"1. 浏览器打开：{web}",
        "2. 直接对话，无需加微信好友、无需扫码",
        "",
        "若朋友坚持用微信：",
        "• 可让管理员提供 LiMa 专用小号加好友（PC 微信桥，见 docs/WECHAT_REAL_DEVICE_WINDOWS.md），",
        "  或使用管理员已绑定的 ClawBot 私聊（仅管理员本人可靠）。",
        "• 请勿再扫本消息里的 liteapp 添加链接（该链接无效于访客接入）。",
        "",
        "管理员自测：",
        "• 请只在「你已扫码登录的那个 ClawBot 对话」里发消息；",
        "• 若这里能回复而朋友不能，即符合上述平台限制。",
    ]
    if bid:
        lines.append(f"\n（运维）当前机器人：{bid}")
    lines.extend([
        "",
        f"官网：{BRAND_SITE}",
        "",
        f"—— {COMPANY_NAME} · LiMa",
    ])
    return "\n".join(lines)
