"""Static outbound copy, help text, and reply formatting for channel gateway."""

from __future__ import annotations

from channel_gateway.branding import maybe_brand_footer

WELCOME_GUEST = (
    "欢迎使用 LiMa 微信助手（动力巢科技）！加好友即可用，无需绑定码。\n"
    "支持：文字聊天 · 语音消息 · 图片/文件分析 · /menu 实用工具。\n"
    "发 /公司 了解我们，/help 看全部命令。\n"
)

TIP_FOOTER = "提示：发「菜单」「官网」「帮助」也行 · /reset 清空对话"

OWNER_ONLY_HELP_HINT = (
    "该命令仅主人可用（需 /bind 操作员码）。"
    "访客可用：聊天、/code、/draw、/menu 工具等。"
)

HELP_TEXT = (
    "LiMa 微信助手（动力巢科技）\n"
    "——\n"
    "直接发文字即可聊天（会记住最近几轮）。\n"
    "发语音条 → 自动转写后回答；发图片/文件 → 自动分析摘要。\n"
    "/help — 本帮助\n"
    "/menu — 联网工具（天气、百科、算式等）\n"
    "/公司 — 动力巢科技与 LiMa 介绍\n"
    "/邀请 — 转发网页入口给朋友（见 chat.donglicao.com）\n"
    "/语音 — 语音使用说明\n"
    "/语音回复 on|off — 是否附带语音条回复（需 LIMA_CHANNEL_VOICE_REPLY=1）\n"
    "/文件 — 文件分析说明\n"
    "/demo — 推荐体验顺序\n"
    "/about — 关于 LiMa\n"
    "/code <问题> — 代码讲解\n"
    "/draw <文字> — 路径绘制预览\n"
    "/reset — 清空会话\n"
    "/pause · /resume · /unbind · /bind <码>\n"
    "主人：/简报 /github /code-task /device /status /memory"
)

VOICE_HELP = (
    "【语音交互】\n"
    "直接发送微信语音条即可。\n"
    "· 若微信已带转写文字，会优先使用\n"
    "· 否则使用小米 MiMo 语音模型转写（与 TTS 共用 MIMO_TTS_KEY）\n"
    "· 备用：Groq / SiliconFlow Whisper\n"
    "· 识别后按普通聊天回答，/reset 可清空上下文"
)

FILE_HELP = (
    "【文件 / 图片分析】\n"
    "· 图片：发送照片，可附带文字说明你的问题\n"
    "· 文件：支持 .txt .md .py .json .csv .pdf 等（单文件约 1.5MB 内）\n"
    "· 其他格式请截图或粘贴关键文字\n"
    "分析结果由 LiMa 多后端路由生成，仅供访客演示与办公辅助。"
)

ABOUT_TEXT = (
    "LiMa 是动力巢科技旗下的个人编码与硬件助手。\n"
    "微信入口：文字/语音/图片/文件分析 + /menu 实用工具。\n"
    "完整能力（代码任务、设备、记忆）请用 LiMa IDE 或 chat.donglicao.com。\n"
    "我是 LiMa，不是 Hermes。发 /公司 查看公司与产品简介。"
)


def finalize_outbound(text: str) -> str:
    return maybe_brand_footer(text or "")


def demo_text() -> str:
    lines = [
        "LiMa 体验路线：",
        "1. 直接问一个问题（例如：Python 里 async 是什么）",
        "2. /算 123*456 — 计算器",
        "3. /百科 Python — 维基摘要",
        "4. /code 用列表推导式过滤空字符串",
        "5. /draw LiMa — 路径预览",
        "6. /menu — 全部联网工具",
        "7. /reset — 清空对话记忆",
        "主人：/简报 · /github owner/repo path",
    ]
    try:
        from channel_gateway.chat_session import max_turns, session_enabled

        if session_enabled():
            lines[1] = f"1. 直接发消息（保留最近 {max_turns()} 轮）"
    except ImportError:
        pass
    return "\n".join(lines)
