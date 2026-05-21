"""
LiMa Identity Guard — 身份/能力问题拦截器

检测用户询问模型身份或能力的问题，直接返回预设回答。
不走任何后端，不消耗配额，响应时间 <1ms。
"""

import re

# ── 身份问题检测模式 ─────────────────────────────────────────────────────────

_IDENTITY_PATTERNS = [
    # 中文身份问题
    r"你是谁", r"你叫什么", r"你是什么模型", r"你的名字",
    r"你是哪个", r"你是哪家", r"谁开发的你", r"谁做的你",
    r"你是ai吗", r"你是人工智能吗", r"你是机器人吗",
    r"你背后是什么", r"你用的什么模型", r"你基于什么",
    # 英文身份问题
    r"who are you", r"what are you", r"what model",
    r"what is your name", r"your name", r"what AI",
    r"are you (gpt|claude|gemini|deepseek|qwen|llama)",
    r"which (model|llm|ai)", r"who made you", r"who built you",
    r"who created you", r"what company",
]

_CAPABILITY_PATTERNS = [
    # 中文能力问题
    r"你能做什么", r"你有什么能力", r"你会什么",
    r"你能帮我做什么", r"你的功能", r"你擅长什么",
    r"你可以做什么", r"介绍一下你自己", r"自我介绍",
    # 英文能力问题
    r"what can you do", r"what are your capabilities",
    r"what are you capable of", r"introduce yourself",
    r"tell me about yourself", r"what do you do",
    r"what are your (skills|abilities|features)",
]

_identity_re = re.compile(
    "|".join(_IDENTITY_PATTERNS), re.IGNORECASE
)
_capability_re = re.compile(
    "|".join(_CAPABILITY_PATTERNS), re.IGNORECASE
)

# ── 预设回答 ─────────────────────────────────────────────────────────────────

IDENTITY_ANSWER_CN = """我是 LiMa（力码），由深圳市动力巢科技有限公司开发的智能编程助手。

我通过智能路由系统调度多个 AI 后端，为你匹配最优解答。"""

IDENTITY_ANSWER_EN = """I'm LiMa, an intelligent programming assistant developed by DongLiCao Technology (Shenzhen).

I use a smart routing system to orchestrate multiple AI backends and match you with the best answer."""

CAPABILITY_ANSWER_CN = """我是 LiMa（力码），我擅长：

- 编程开发（Python, JavaScript, TypeScript, Rust, Go, C/C++ 等主流语言）
- 嵌入式系统（ESP32, STM32, Arduino, GRBL）
- 数据分析与算法设计
- 技术方案设计与架构评审
- 文档写作与代码审查
- 多语言翻译与技术解释

我通过智能路由系统调度多个 AI 后端，为你匹配最优解答。有什么我可以帮你的？"""

CAPABILITY_ANSWER_EN = """I'm LiMa, and here's what I can help with:

- Programming (Python, JavaScript, TypeScript, Rust, Go, C/C++ and more)
- Embedded systems (ESP32, STM32, Arduino, GRBL)
- Data analysis and algorithm design
- Technical architecture and code review
- Documentation and technical writing
- Multilingual translation and explanation

I route your questions to the best AI backend for optimal answers. How can I help?"""


# ── 检测函数 ─────────────────────────────────────────────────────────────────

def _is_chinese(text: str) -> bool:
    """判断文本是否主要是中文。"""
    cn_chars = sum(1 for c in text if '一' <= c <= '鿿')
    return cn_chars > len(text) * 0.1


def detect_identity_question(query: str) -> str | None:
    """
    检测是否为身份/能力类问题。
    返回: 预设回答字符串，或 None（非身份问题）。
    """
    if not query or len(query) > 200:
        return None

    q = query.strip()
    is_cn = _is_chinese(q)

    if _identity_re.search(q):
        return IDENTITY_ANSWER_CN if is_cn else IDENTITY_ANSWER_EN

    if _capability_re.search(q):
        return CAPABILITY_ANSWER_CN if is_cn else CAPABILITY_ANSWER_EN

    return None
