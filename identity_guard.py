"""
LiMa Identity Guard — 身份/能力问题拦截器

检测用户询问模型身份或能力的问题，直接返回预设回答。
不走任何后端，不消耗配额，响应时间 <1ms。
"""

import re

import brand_config
from identity_guard_patterns import matches_capability_question, matches_identity_question

_NAME = brand_config.PUBLIC_MODEL_NAME
_NAME_CN = brand_config.PUBLIC_MODEL_NAME_CN
_COMPANY_CN = brand_config.COMPANY_NAME_CN
_COMPANY_EN = brand_config.COMPANY_NAME_EN
_COMPANY_SHORT_CN = brand_config.COMPANY_SHORT_CN

IDENTITY_ANSWER_CN = f"""我是 {_NAME}（{_NAME_CN}），由{_COMPANY_CN}开发的智能助手。

我具备联网能力，可以实时查询{brand_config.CAPABILITY_SUMMARY_CN}。有什么可以帮你的？"""

IDENTITY_ANSWER_EN = f"""I'm {_NAME}, an intelligent assistant by {_COMPANY_EN}.

I have internet access and can query real-time {brand_config.CAPABILITY_SUMMARY_EN}. How can I help?"""

_CAP_BULLETS_CN = "\n".join(f"- {v}" for v in brand_config.CAPABILITY_BULLETS_CN.values())
_CAP_BULLETS_EN = "\n".join(f"- {v}" for v in brand_config.CAPABILITY_BULLETS_EN.values())

CAPABILITY_ANSWER_CN = f"""我是 {_NAME}（{_NAME_CN}），我的能力：

{_CAP_BULLETS_CN}

有什么需要帮忙的？"""

CAPABILITY_ANSWER_EN = f"""I'm {_NAME}. My capabilities:

{_CAP_BULLETS_EN}

How can I help?"""

# ── 访客 / 公开频道：保守能力声明 ───────────────────────────────────────────

IDENTITY_ANSWER_GUEST_CN = f"""我是 {_NAME}（{_NAME_CN}），面向访客的公开体验助手。

本频道提供编程问答、基础说明与演示功能，不包含完整个人后台或私有设备控制。有什么可以帮你的？"""

IDENTITY_ANSWER_GUEST_EN = f"""I'm {_NAME}, a public demo assistant for guests.

This channel offers coding Q&A, explanations, and demos. Full owner-only features are not available here. How can I help?"""

CAPABILITY_ANSWER_GUEST_CN = f"""我是 {_NAME}（{_NAME_CN}），访客频道可用能力：

- 编程问答与代码解释
- 基础聊天与演示说明
- 不涉及私有仓库、任务执行或设备控制

如需完整能力，请通过 owner 入口使用。"""

CAPABILITY_ANSWER_GUEST_EN = f"""I'm {_NAME}. Guest channel capabilities:

- Coding Q&A and explanations
- Basic chat and demo guidance
- No private repo access, task execution, or device control

Use the owner entry for full capabilities."""

# 泄露替换用的短回答（非整段能力清单）
SHORT_LEAK_REPLACEMENT_CN = f"我是 {_NAME}（{_NAME_CN}），由{_COMPANY_SHORT_CN}开发的智能助手。"
SHORT_LEAK_REPLACEMENT_EN = f"I'm {_NAME}, an assistant by {_COMPANY_EN}."


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

    if matches_identity_question(q):
        return id_cn if is_cn else id_en

    if matches_capability_question(q):
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
