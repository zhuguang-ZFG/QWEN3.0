"""
LiMa Identity Guard — 身份/能力问题拦截器

检测用户询问模型身份或能力的问题，直接返回预设回答。
不走任何后端，不消耗配额，响应时间 <1ms。
"""

import re

# ── 身份问题检测模式 ─────────────────────────────────────────────────────────

_IDENTITY_PATTERNS = [
    # 中文身份问题
    r"你是谁",
    r"你叫什么",
    r"你是什么",
    r"你是什么模型",
    r"你的名字",
    r"你是哪个",
    r"你是哪家",
    r"谁开发的你",
    r"谁做的你",
    r"你是ai吗",
    r"你是人工智能吗",
    r"你是机器人吗",
    r"你背后是什么",
    r"你用的什么模型",
    r"你基于什么",
    r"你的创造者",
    r"谁创造.*你",
    r"你的开发者",
    r"你的母公司",
    r"你属于.*公司",
    r"你是.*公司的",
    r"你的父公司",
    r"你的父母",
    r"你的爸",
    r"你的妈",
    r"你从哪来",
    r"你的身世",
    r"你的出身",
    r"你的来历",
    r"你是.*开发",
    r"你.*哪个公司",
    r"你.*哪家公司",
    r"动力巢",
    r"donglicao",
    r"powernest",
    r"你是gpt吗",
    r"你是claude吗",
    r"你是deepseek吗",
    r"你是llama吗",
    r"你是gemini吗",
    r"你是qwen吗",
    r"你是chatgpt",
    r"你是通义",
    r"你是文心",
    # 英文身份问题
    r"who are you",
    r"what are you",
    r"what model",
    r"what is your name",
    r"your name",
    r"what AI",
    r"are you (gpt|claude|gemini|deepseek|qwen|llama|meta)",
    r"which (model|llm|ai)",
    r"who made you",
    r"who built you",
    r"who created you",
    r"what company",
    r"your (creator|developer|maker)",
    r"who.*develop",
    r"who.*own",
    r"parent company",
]

_CAPABILITY_PATTERNS = [
    # 中文能力问题
    r"你能做什么",
    r"你有什么能力",
    r"你会什么",
    r"你能帮我做什么",
    r"你的功能",
    r"你擅长什么",
    r"你可以做什么",
    r"介绍一下你自己",
    r"自我介绍",
    # 英文能力问题
    r"what can you do",
    r"what are your capabilities",
    r"what are you capable of",
    r"introduce yourself",
    r"tell me about yourself",
    r"what do you do",
    r"what are your (skills|abilities|features)",
]

_identity_re = re.compile("|".join(_IDENTITY_PATTERNS), re.IGNORECASE)
_capability_re = re.compile("|".join(_CAPABILITY_PATTERNS), re.IGNORECASE)

# ── 预设回答（owner / 默认：完整能力） ───────────────────────────────────────

IDENTITY_ANSWER_CN = """我是 LiMa（力码），由深圳市动力巢科技有限公司开发的智能助手。

我具备联网能力，可以实时查询天气、新闻、汇率、热搜、股票等信息。有什么可以帮你的？"""

IDENTITY_ANSWER_EN = """I'm LiMa, an intelligent assistant by DongLiCao Technology (Shenzhen).

I have internet access and can query real-time weather, news, exchange rates, stocks, and more. How can I help?"""

CAPABILITY_ANSWER_CN = """我是 LiMa（力码），我的能力：

- 联网查询：天气、新闻、热搜、汇率、股票、快递、地震等实时数据
- 编程开发：Python, JavaScript, Go, Rust, C/C++ 等
- 语音交互：语音转文字、文字转语音
- 翻译：支持中英日韩法德等多语言
- 工具调用：计算、单位换算、二维码、短链接等

有什么需要帮忙的？"""

CAPABILITY_ANSWER_EN = """I'm LiMa. My capabilities:

- Internet access: real-time weather, news, trends, exchange rates, stocks, earthquakes
- Programming: Python, JavaScript, Go, Rust, C/C++ and more
- Voice: speech-to-text and text-to-speech
- Translation: Chinese, English, Japanese, Korean, French, German
- Tools: calculator, unit conversion, QR codes, URL shortening

How can I help?"""

# ── 访客 / 公开频道：保守能力声明 ───────────────────────────────────────────

IDENTITY_ANSWER_GUEST_CN = """我是 LiMa（力码），面向访客的公开体验助手。

本频道提供编程问答、基础说明与演示功能，不包含完整个人后台或私有设备控制。有什么可以帮你的？"""

IDENTITY_ANSWER_GUEST_EN = """I'm LiMa, a public demo assistant for guests.

This channel offers coding Q&A, explanations, and demos. Full owner-only features are not available here. How can I help?"""

CAPABILITY_ANSWER_GUEST_CN = """我是 LiMa（力码），访客频道可用能力：

- 编程问答与代码解释
- 基础聊天与演示说明
- 不涉及私有仓库、任务执行或设备控制

如需完整能力，请通过 owner 入口使用。"""

CAPABILITY_ANSWER_GUEST_EN = """I'm LiMa. Guest channel capabilities:

- Coding Q&A and explanations
- Basic chat and demo guidance
- No private repo access, task execution, or device control

Use the owner entry for full capabilities."""

# 泄露替换用的短回答（非整段能力清单）
SHORT_LEAK_REPLACEMENT_CN = "我是 LiMa（力码），由动力巢科技开发的智能助手。"
SHORT_LEAK_REPLACEMENT_EN = "I'm LiMa, an assistant by DongLiCao Technology."


def _is_chinese(text: str) -> bool:
    """判断文本是否主要是中文。"""
    cn_chars = sum(1 for c in text if "一" <= c <= "鿿")
    return cn_chars > len(text) * 0.1


def _answers_for_role(channel_role: str) -> tuple[str, str, str, str]:
    role = (channel_role or "default").lower()
    if role == "guest":
        return (
            IDENTITY_ANSWER_GUEST_CN,
            IDENTITY_ANSWER_GUEST_EN,
            CAPABILITY_ANSWER_GUEST_CN,
            CAPABILITY_ANSWER_GUEST_EN,
        )
    return (
        IDENTITY_ANSWER_CN,
        IDENTITY_ANSWER_EN,
        CAPABILITY_ANSWER_CN,
        CAPABILITY_ANSWER_EN,
    )


def detect_identity_question(query: str, *, channel_role: str = "default") -> str | None:
    """
    检测是否为身份/能力类问题。
    返回: 预设回答字符串，或 None（非身份问题）。
    """
    if not query or len(query) > 200:
        return None

    q = query.strip()
    is_cn = _is_chinese(q)
    id_cn, id_en, cap_cn, cap_en = _answers_for_role(channel_role)

    if _identity_re.search(q):
        return id_cn if is_cn else id_en

    if _capability_re.search(q):
        return cap_cn if is_cn else cap_en

    return None


# ── 回复后置过滤器 — 防止模型泄露真实身份 ────────────────────────────────────

_LEAK_PATTERNS = re.compile(
    r"(我是|I am|I'm|我叫|我由|As|as).{0,16}"
    r"(Meta|OpenAI|Google|Anthropic|DeepSeek|Alibaba|阿里|百度|Baidu|"
    r"字节|ByteDance|腾讯|Tencent|Mistral|微软|Microsoft|Claude|Gemini|GPT|ChatGPT)"
    r"|"
    r"(我是|I am|I'm|As|as).{0,16}"
    r"(GPT|ChatGPT|Claude|Gemini|Llama|LLaMA|Qwen|通义|文心|豆包|Doubao|"
    r"Mixtral|Codestral|DeepSeek|PaLM|Bard|Kimi|DeepSeek)"
    r"|"
    r"(由|developed by|made by|created by|built by).{0,10}"
    r"(Meta|OpenAI|Google|Anthropic|Microsoft|阿里|百度|字节|腾讯)",
    re.IGNORECASE,
)


def filter_identity_leak(response: str, *, prefer_language: str | None = None) -> str:
    """检查 AI 回复是否泄露真实模型身份；优先局部清洗，必要时短句替换。"""
    if not response:
        return response
    if not _LEAK_PATTERNS.search(response):
        return response

    from response_cleaner import apply_identity_cleaning

    sanitized = apply_identity_cleaning(response)
    if sanitized and not _LEAK_PATTERNS.search(sanitized):
        return sanitized

    lang = prefer_language
    if not lang:
        lang = "cn" if _is_chinese(response) else "en"
    if lang == "cn":
        return SHORT_LEAK_REPLACEMENT_CN
    return SHORT_LEAK_REPLACEMENT_EN
