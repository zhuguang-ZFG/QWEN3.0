"""Layer 1: request type and scenario classification (CQ-014 slice 11)."""

from __future__ import annotations

import router_v3


def classify(query: str, messages: list[dict], *,
             fmt: str = "openai", ide_source: str = "",
             system_prompt: str = "", headers: dict = None) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        return "ide"

    if ide_source and ide_source in router_v3.IDE_SOURCES:
        return "ide"

    ua = headers.get("user-agent", "").lower()
    if any(x in ua for x in ["claude-code", "cursor", "aider", "codex", "cline", "continue", "vscode", "kiro", "zed", "trae", "windsurf", "copilot"]):
        return "ide"

    if system_prompt and router_v3.detect_ide_from_system_prompt(system_prompt):
        return "ide"

    if _has_image_blocks(messages):
        return "vision"

    return "chat"


def classify_scenario(query: str, messages: list[dict], *,
                      ide_source: str = "", request_type: str = "") -> str:
    """判断场景: coding / chat。决定走质量路径还是速度路径。"""
    if request_type == "ide":
        return "coding"
    if ide_source and ide_source.lower() in (
        "claude code", "cursor", "aider", "cline", "codex",
        "continue", "vscode", "vs code",
    ):
        return "coding"

    last_content = ""
    if messages:
        last = messages[-1]
        last_content = last.get("content", "") if isinstance(last, dict) else ""
        if isinstance(last_content, list):
            last_content = " ".join(
                b.get("text", "") for b in last_content if isinstance(b, dict))

    text = last_content or query

    if "```" in text:
        return "coding"
    if any(kw in text for kw in ("Traceback", "Error:", "TypeError", "SyntaxError")):
        return "coding"

    code_signals = ("def ", "class ", "import ", "function ", "const ", "async ",
                    "return ", "if __name__", "from ", "export ")
    if sum(1 for s in code_signals if s in text) >= 2:
        return "coding"

    import re
    if re.search(r'\w+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp)\b', text):
        return "coding"

    return "chat"


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False
