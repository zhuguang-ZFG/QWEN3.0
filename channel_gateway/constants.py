"""Channel Gateway constants and help texts."""

# Command restrictions
CMD_ALLOWED_WHEN_PAUSED = frozenset({"resume", "unbind", "help"})
CMD_ALLOWED_WHEN_UNBOUND = frozenset({"bind", "help"})

# Welcome messages
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

# Help texts
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
    "【文件/图片分析】\n"
    "发送图片、PDF、Word、Excel、代码文件等，自动分析生成摘要。\n"
    "支持多格式：文档、图表、代码、手写、电子表格。\n"
    "也可附加指令：先发文件，紧接着发「用英语翻译」或「这段代码有什么bug」。"
)

ABOUT_TEXT = (
    "LiMa 是动力巢科技旗下的个人编码与硬件助手。\n"
    "微信入口：文字/语音/图片/文件分析 + /menu 实用工具。\n"
    "完整能力（代码任务、设备、记忆）请用 LiMa IDE 或 chat.donglicao.com。\n"
    "我是 LiMa，不是 Hermes。发 /公司 查看公司与产品简介。"
)
