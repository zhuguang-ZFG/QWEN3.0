"""Guest onboarding — web chat only (WeChat channels retired)."""

from __future__ import annotations

from channel_gateway.branding import BRAND_SITE, COMPANY_NAME, PRODUCT_SITE


def invite_text(*, bot_id: str = "", share_url: str = "") -> str:
    """Forward to friends: use LiMa web chat; WeChat bots/liteapp/WCF/iLink are retired."""
    del bot_id, share_url
    web = PRODUCT_SITE
    return "\n".join([
        "【LiMa 访客说明 — 请转发给朋友】",
        "",
        "请用浏览器（推荐，无需安装）：",
        f"• {web}",
        "",
        "微信相关入口已停用：",
        "• 不再提供微信加好友、ClawBot 机器人、liteapp 链接。",
        "• 详情见 docs/WECHAT_RETIRED.md",
        "",
        f"官网：{BRAND_SITE}",
        "",
        f"—— {COMPANY_NAME} · LiMa",
    ])
