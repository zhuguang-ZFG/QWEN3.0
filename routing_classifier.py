"""Layer 1: request type and scenario classification (CQ-014 slice 11)."""

from __future__ import annotations

import re

import router_v3


def classify(
    query: str,
    messages: list[dict],
    *,
    fmt: str = "openai",
    ide_source: str = "",
    system_prompt: str = "",
    headers: dict = None,
) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        return "ide"

    if ide_source and ide_source.lower() in _IDE_SOURCES:
        return "ide"

    ua = headers.get("user-agent", "").lower()
    if any(
        x in ua
        for x in [
            "claude-code",
            "cursor",
            "aider",
            "codex",
            "cline",
            "continue",
            "vscode",
            "kiro",
            "zed",
            "trae",
            "windsurf",
            "copilot",
        ]
    ):
        return "ide"

    if system_prompt and router_v3.detect_ide_by_fingerprints(system_prompt):
        return "ide"

    if _has_image_blocks(messages):
        return "vision"

    return "chat"


_IDE_SOURCES = frozenset(
    {
        "claude code",
        "cursor",
        "aider",
        "cline",
        "codex",
        "continue",
        "vscode",
        "vs code",
    }
)

_GENERIC_CODE_SIGNALS = (
    "def ",
    "class ",
    "import ",
    "function ",
    "const ",
    "async ",
    "return ",
    "if __name__",
    "from ",
    "export ",
)

_CN_CODE_SIGNALS = (
    "写一个",
    "写个",
    "编写",
    "实现",
    "函数",
    "代码",
    "编程",
    "开发",
    "重构",
    "修复",
    "调试",
    "测试",
    "Python",
    "JavaScript",
    "Golang",
    "Rust",
    "Java",
)

_EN_CODE_SIGNALS = (
    "write a",
    "implement",
    "create a function",
    "sort",
    "algorithm",
    "function",
    "code",
    "fix bug",
    "refactor",
    "test case",
)

_FILE_EXT_RE = re.compile(r"\w+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp)\b")


def classify_scenario(messages, query=None, ide_source=None, request_type=None) -> str:
    """判断场景: coding / chat。决定走质量路径还是速度路径。"""
    if isinstance(messages, str) and isinstance(query, list):
        messages, query = query, messages

    if request_type == "ide":
        return "coding"
    if ide_source and ide_source.lower() in _IDE_SOURCES:
        return "coding"

    text = _extract_text(messages, query)

    if _has_strong_code_signal(text):
        return "coding"
    if _count_intent_signals(_GENERIC_CODE_SIGNALS, text) >= 2:
        return "coding"
    if _count_intent_signals(_CN_CODE_SIGNALS, text) >= 2:
        return "coding"
    if _count_intent_signals(_EN_CODE_SIGNALS, text, lower=True) >= 2:
        return "coding"
    if _has_file_extension(text):
        return "coding"

    return "chat"


def _extract_text(messages, query) -> str:
    last_content = ""
    if messages:
        last = messages[-1]
        last_content = last.get("content", "") if isinstance(last, dict) else ""
        if isinstance(last_content, list):
            last_content = " ".join(b.get("text", "") for b in last_content if isinstance(b, dict))
    return last_content or query or ""


def _has_strong_code_signal(text: str) -> bool:
    strong_signals = ("Traceback", "Error:", "TypeError", "SyntaxError")
    return "```" in text or any(kw in text for kw in strong_signals)


def _count_intent_signals(signals: tuple[str, ...], text: str, *, lower: bool = False) -> int:
    if lower:
        text = text.lower()
        return sum(1 for s in signals if s.lower() in text)
    return sum(1 for s in signals if s in text)


def _has_file_extension(text: str) -> bool:
    return bool(_FILE_EXT_RE.search(text))


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False
