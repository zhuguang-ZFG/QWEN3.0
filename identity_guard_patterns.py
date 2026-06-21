"""Identity guard pattern matching — keywords first, regex for complex patterns only."""

from __future__ import annotations

import re

_IDENTITY_KEYWORDS = frozenset(
    {
        "你是谁",
        "你叫什么",
        "你是什么",
        "你是什么模型",
        "你的名字",
        "你是哪个",
        "你是哪家",
        "谁开发的你",
        "谁做的你",
        "你是ai吗",
        "你是人工智能吗",
        "你是机器人吗",
        "你背后是什么",
        "你用的什么模型",
        "你基于什么",
        "你的创造者",
        "你的开发者",
        "你的母公司",
        "你的父公司",
        "你的父母",
        "你的爸",
        "你的妈",
        "你从哪来",
        "你的身世",
        "你的出身",
        "你的来历",
        "动力巢",
        "donglicao",
        "powernest",
        "你是gpt吗",
        "你是claude吗",
        "你是deepseek吗",
        "你是llama吗",
        "你是gemini吗",
        "你是qwen吗",
        "你是chatgpt",
        "你是通义",
        "你是文心",
        "who are you",
        "what are you",
        "what model",
        "what is your name",
        "your name",
        "what ai",
        "who made you",
        "who built you",
        "who created you",
        "what company",
        "your creator",
        "your developer",
        "your maker",
        "parent company",
    }
)

_IDENTITY_COMPLEX_RE = re.compile(
    "|".join(
        (
            r"谁创造.*你",
            r"你属于.*公司",
            r"你是.*公司的",
            r"你是.*开发",
            r"你.*哪个公司",
            r"你.*哪家公司",
            r"are you (gpt|claude|gemini|deepseek|qwen|llama|meta)",
            r"which (model|llm|ai)",
            r"who.*develop",
            r"who.*own",
        )
    ),
    re.IGNORECASE,
)

_CAPABILITY_KEYWORDS = frozenset(
    {
        "你能做什么",
        "你有什么能力",
        "你会什么",
        "你能帮我做什么",
        "你的功能",
        "你擅长什么",
        "你可以做什么",
        "介绍一下你自己",
        "自我介绍",
        "what can you do",
        "what are your capabilities",
        "what are you capable of",
        "introduce yourself",
        "tell me about yourself",
        "what do you do",
    }
)

_CAPABILITY_COMPLEX_RE = re.compile(
    r"what are your (skills|abilities|features)",
    re.IGNORECASE,
)


def matches_identity_question(query: str) -> bool:
    q = query.strip()
    if not q:
        return False
    q_lower = q.lower()
    if any(keyword in q_lower for keyword in _IDENTITY_KEYWORDS):
        return True
    return _IDENTITY_COMPLEX_RE.search(q) is not None


def matches_capability_question(query: str) -> bool:
    q = query.strip()
    if not q:
        return False
    q_lower = q.lower()
    if any(keyword in q_lower for keyword in _CAPABILITY_KEYWORDS):
        return True
    return _CAPABILITY_COMPLEX_RE.search(q) is not None
