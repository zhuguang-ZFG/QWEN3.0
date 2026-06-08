"""Channel Gateway helper functions."""

import os
import re

from channel_gateway.branding import maybe_brand_footer


def auto_guest_bind_enabled() -> bool:
    """Check if auto guest binding is enabled via env var."""
    return os.environ.get("LIMA_CHANNEL_AUTO_GUEST_BIND", "1") == "1"


def is_greeting(text: str) -> bool:
    """Check if text is a simple greeting."""
    return bool(re.match(r"^(你好|hi|hello|嗨)$", text.strip().lower()))


def greeting_reply() -> str:
    """Generate a greeting reply for new guests."""
    return maybe_brand_footer(
        "你好，我是 LiMa 微信助手（动力巢科技）。\n"
        "可打字、发语音、发图片/文件；发「菜单」或用 /menu。\n"
        "发「官网」或 /公司 了解我们，「帮助」或 /help 看命令。"
    )


def finalize_outbound(text: str) -> str:
    """Add optional branding footer to outbound text."""
    return maybe_brand_footer(text)


def demo_text() -> str:
    """Generate demo/walkthrough text."""
    return (
        "【推荐体验顺序】\n"
        "1️⃣ 直接发消息聊天（记住最近几轮）\n"
        "2️⃣ 发送语音条，自动转写后回答\n"
        "3️⃣ 发送图片/文件，AI 自动分析\n"
        "4️⃣ /menu 试试联网工具（天气、百科、算式）\n"
        "5️⃣ /code <问题> 代码讲解\n"
        "6️⃣ /draw <描述> 路径绘制预览\n"
        "7️⃣ /邀请 转发网页入口给朋友\n"
        "8️⃣ /公司 了解动力巢科技\n"
        "\n"
        "提示：发「菜单」「帮助」也行 · /reset 清空对话"
    )
