"""Hermes Agent Gateway API client (Mode 3: true agent execution).

Posts autonomous tasks to Hermes Gateway (persistent server mode on port 18790).
When Gateway is running, Hermes Agent executes multi-step tasks with tool calls
(file ops, shell, browser, web search) — going beyond LiMa's single-turn routing.

Fallback: If Gateway is unreachable, hermes_bridge.call_hermes_agent() degrades
to call_lima_structured() (OpenAI SDK call via LiMa's routing pipeline).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

HERMES_GATEWAY_PORT = int(os.environ.get("HERMES_GATEWAY_PORT", "18790"))
HERMES_GATEWAY_BASE = f"http://127.0.0.1:{HERMES_GATEWAY_PORT}"


def _check_gateway() -> bool:
    """Check if Hermes Gateway is running."""
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{HERMES_GATEWAY_BASE}/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_agent_task(
    prompt: str,
    *,
    task_type: str = "chat",
    model: str = "lima-1.3",
    toolsets: list[str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Send a task to Hermes Agent Gateway for autonomous execution.

    Args:
        prompt: The task prompt.
        task_type: 'code_exec', 'file_ops', 'browser', 'research', 'chat'.
        model: Model to use (default: LiMa via custom:lima).
        toolsets: Tool categories to enable. None = auto-detect from task_type.
        timeout: Max execution time in seconds.

    Returns:
        Dict with keys: 'response', 'task_id', 'tool_calls', 'steps', 'success'.
    """
    if not _check_gateway():
        raise RuntimeError("Hermes Gateway not reachable on port " + str(HERMES_GATEWAY_PORT))

    import urllib.request

    task_id = f"lima-{uuid.uuid4().hex[:8]}"
    body = json.dumps(
        {
            "task_id": task_id,
            "prompt": prompt,
            "task_type": task_type,
            "model": model,
            "toolsets": toolsets or _default_toolsets(task_type),
            "max_turns": 20,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{HERMES_GATEWAY_BASE}/tasks",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.exception("hermes_gateway: task failed")
        return {
            "response": f"[Hermes Gateway Error: {e}]",
            "task_id": task_id,
            "tool_calls": [],
            "steps": 0,
            "success": False,
        }

    return {
        "response": data.get("response", ""),
        "task_id": task_id,
        "tool_calls": data.get("tool_calls", []),
        "steps": data.get("steps", 0),
        "success": data.get("success", True),
    }


def _default_toolsets(task_type: str) -> list[str]:
    """Map task type to default tool categories."""
    mapping = {
        "code_exec": ["shell", "file"],
        "file_ops": ["file"],
        "browser": ["browser", "file"],
        "research": ["web", "file"],
        "chat": [],
    }
    return mapping.get(task_type, [])
