"""
Tool forward - Simplified stub for strategic pivot.

原 tool_forward.py 已删除（编码助手专属工具调用）。
此文件提供最小占位符，避免大量修改 server.py。
Phase 2 将重构为设备场景专用的工具调用（如有需要）。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

_log = logging.getLogger(__name__)

# Constants
TOOL_TIER1_BACKENDS = ["openrouter", "openai"]
ANTHROPIC_NATIVE_BACKENDS = ["anthropic", "bedrock"]

# State
_record_request = None
_model_id = "lima-1.3"


def inject_state(record_request: Any, model_id: str) -> None:
    """注入状态（占位符）"""
    global _record_request, _model_id
    _record_request = record_request
    _model_id = model_id


async def anthropic_native_forward(body: dict[str, Any]) -> dict[str, Any]:
    """Anthropic 原生转发（占位符）"""
    # TODO Phase 2: 实现设备场景的工具调用（如有需要）
    _log.warning("[STUB] anthropic_native_forward called")
    return {
        "type": "error",
        "error": {
            "type": "not_implemented",
            "message": "Tool calls not implemented in device mode",
        },
    }


async def anthropic_native_stream(body: dict[str, Any]) -> AsyncIterator[str]:
    """Anthropic 原生流式转发（占位符）"""
    # TODO Phase 2: 实现设备场景的工具调用（如有需要）
    _log.warning("[STUB] anthropic_native_stream called")
    yield 'data: {"type":"error","error":{"type":"not_implemented","message":"Tool stream not implemented"}}\n\n'


async def simulate_anthropic_sse(response: dict[str, Any]) -> AsyncIterator[str]:
    """模拟 Anthropic SSE（占位符）"""
    # TODO Phase 2: 实现设备场景的 SSE（如有需要）
    _log.warning("[STUB] simulate_anthropic_sse called")
    yield 'data: {"type":"error","error":{"type":"not_implemented","message":"SSE not implemented"}}\n\n'


async def tool_call_forward(body: dict[str, Any]) -> dict[str, Any]:
    """工具调用转发（占位符）"""
    # TODO Phase 2: 实现设备场景的工具调用（如有需要）
    _log.warning("[STUB] tool_call_forward called")
    return {
        "error": {
            "message": "Tool calls not implemented in device mode",
            "type": "not_implemented",
        }
    }


async def tool_call_stream(body: dict[str, Any]) -> AsyncIterator[str]:
    """工具调用流式转发（占位符）"""
    # TODO Phase 2: 实现设备场景的工具调用（如有需要）
    _log.warning("[STUB] tool_call_stream called")
    yield 'data: {"error":{"message":"Tool stream not implemented","type":"not_implemented"}}\n\n'


def pick_tool_backend(backend_enabled: dict[str, bool]) -> str | None:
    """选择工具后端（占位符）"""
    # TODO Phase 2: 实现设备场景的后端选择（如有需要）
    for backend in TOOL_TIER1_BACKENDS:
        if backend_enabled.get(backend, False):
            return backend
    return None


def iter_tool_backends(backend_enabled: dict[str, bool]) -> list[str]:
    """迭代工具后端（占位符）"""
    # TODO Phase 2: 实现设备场景的后端迭代（如有需要）
    return [b for b in TOOL_TIER1_BACKENDS if backend_enabled.get(b, False)]
