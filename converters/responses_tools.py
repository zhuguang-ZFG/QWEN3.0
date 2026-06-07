"""Tool schema conversion for the OpenAI Responses API shim."""

from __future__ import annotations

from typing import Any


def responses_tools_to_chat_tools(tools: list | None) -> list[dict] | None:
    if not tools:
        return None
    out: list[dict] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and "function" not in tool and "name" in tool:
            function: dict[str, Any] = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            }
            if "strict" in tool:
                function["strict"] = tool["strict"]
            out.append({"type": "function", "function": function})
        else:
            out.append(tool)
    return out or None


def responses_tool_choice_to_chat_tool_choice(tool_choice: str | dict | None) -> str | dict | None:
    if not isinstance(tool_choice, dict):
        return tool_choice
    if (
        tool_choice.get("type") == "function"
        and isinstance(tool_choice.get("name"), str)
        and "function" not in tool_choice
    ):
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return tool_choice
