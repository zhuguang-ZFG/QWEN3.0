"""Layer 1: request type and scenario classification (CQ-014 slice 11)."""

from __future__ import annotations

import router_v3
from models.structured_outputs import ClassifyResult, ScenarioResult
from models.structured_outputs.validator import validate_value


def classify(
    query: str,
    messages: list[dict],
    *,
    fmt: str = "openai",
    ide_source: str = "",
    system_prompt: str = "",
    headers: dict | None = None,
) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        request_type = "ide"
    elif ide_source and ide_source.lower() in _IDE_SOURCES:
        request_type = "ide"
    elif _user_agent_is_ide(headers.get("user-agent", "")):
        request_type = "ide"
    elif system_prompt and router_v3.detect_ide_by_fingerprints(system_prompt):
        request_type = "ide"
    elif _has_image_blocks(messages):
        request_type = "vision"
    else:
        request_type = "chat"

    validated = validate_value(
        {"request_type": request_type, "confidence": 1.0},
        ClassifyResult,
    )
    return validated.request_type


def _user_agent_is_ide(user_agent: str) -> bool:
    ua = user_agent.lower()
    return any(
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
    )


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


def classify_scenario(
    messages: list[dict] | None,
    *,
    query: str | None = None,
    ide_source: str | None = None,
    request_type: str | None = None,
) -> str:
    """判断场景: chat。v3.0 起编码能力退役，永远返回 chat。"""
    del messages, query, ide_source, request_type
    validated = validate_value({"scenario": "chat", "confidence": 1.0}, ScenarioResult)
    return validated.scenario


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False
