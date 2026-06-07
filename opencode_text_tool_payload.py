"""OpenCode text-tool payload adaptation.

Text-tool backends can emulate tool calls from plain text, but they should not
receive OpenCode's native tool schema. This module decides when to inject a
compact tool prompt and when to keep a request as plain text.
"""

from __future__ import annotations

import re

from text_tool_extractor import TEXT_TOOL_BACKENDS, build_tool_system_prompt

_TOOL_ACTION_RE = re.compile(
    r"\b(read|open|list|grep|search|find|inspect|cat|ls|edit|write|create|"
    r"modify|patch|delete|rename|move)\b",
    re.IGNORECASE,
)
_TOOL_CONTEXT_RE = re.compile(
    r"(\b(file|path|directory|folder|repo|repository|workspace|codebase|"
    r"readme|package\.json|pyproject\.toml|url|web|http|https)\b|"
    r"[A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)",
    re.IGNORECASE,
)
_COMMAND_CONTEXT_RE = re.compile(
    r"\b(bash|shell|terminal|command|cmd|powershell|npm|pytest|git|python -m)\b",
    re.IGNORECASE,
)


def prepare_opencode_text_tool_payload(
    backend: str,
    messages: list[dict],
    tools: list[dict] | None,
    tool_choice: str | dict | None = None,
) -> tuple[list[dict], list[dict] | None, bool]:
    """Return adapted messages, native tools, and whether a tool prompt was added."""
    if backend not in TEXT_TOOL_BACKENDS or not tools:
        return messages, tools, False
    if _should_inject_text_tool_prompt(messages, tools, tool_choice):
        tool_prompt = build_tool_system_prompt(tools)
        return [{"role": "system", "content": tool_prompt}] + list(messages), None, True
    return messages, None, False


def _should_inject_text_tool_prompt(
    messages: list[dict],
    tools: list[dict],
    tool_choice: str | dict | None,
) -> bool:
    if _forced_tool_choice(tool_choice):
        return True
    query = _last_user_text(messages).lower()
    if not query:
        return False
    for name in _tool_names(tools):
        if re.search(
            rf"\b(use|call|run)\s+(?:the\s+tool\s+)?{re.escape(name.lower())}\b",
            query,
        ):
            return True
    if _COMMAND_CONTEXT_RE.search(query):
        return True
    return bool(_TOOL_ACTION_RE.search(query) and _TOOL_CONTEXT_RE.search(query))


def _forced_tool_choice(tool_choice: str | dict | None) -> bool:
    if isinstance(tool_choice, dict):
        return bool((tool_choice.get("function") or {}).get("name"))
    if isinstance(tool_choice, str):
        return tool_choice not in ("", "auto", "none")
    return False


def _tool_names(tools: list[dict]) -> list[str]:
    names = []
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict):
            name = tool["function"].get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return _content_text(message.get("content"))
    return ""


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""
