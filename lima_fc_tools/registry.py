"""Registry for Telegram Function Calling tools."""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

ToolHandler = Callable[..., Awaitable[Any]]
TOOLS: list[dict[str, Any]] = []
_HANDLERS: dict[str, ToolHandler] = {}


def tool(name: str, description: str, parameters: dict[str, Any]):
    """Register a Function Calling tool."""

    def decorator(fn: ToolHandler):
        definition = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        for index, existing in enumerate(TOOLS):
            if existing.get("function", {}).get("name") == name:
                TOOLS[index] = definition
                break
        else:
            TOOLS.append(definition)
        _HANDLERS[name] = fn
        return fn

    return decorator


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a registered tool and return a JSON string."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = await handler(**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        log.error("Tool %s failed: %s", name, exc)
        return json.dumps({"error": str(exc)})


def get_tools_schema() -> list[dict[str, Any]]:
    """Return OpenAI-compatible Function Calling tool schemas."""
    return list(TOOLS)


def stats() -> dict[str, Any]:
    """Return registry statistics."""
    return {"total_tools": len(TOOLS), "tool_names": [t["function"]["name"] for t in TOOLS]}


def registered_handlers() -> dict[str, ToolHandler]:
    """Return a copy of registered handlers for diagnostics."""
    return dict(_HANDLERS)
