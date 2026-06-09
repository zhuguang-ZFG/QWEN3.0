"""
Anthropic stream - Simplified stub for strategic pivot.

原 anthropic_stream.py 已删除（编码助手专属）。
此文件提供最小占位符，避免大量修改 server.py。
Phase 2 将重构为设备场景专用的流式处理。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

_log = logging.getLogger(__name__)

# State placeholder
_deps: dict[str, Any] = {}


def inject_deps(**kwargs: Any) -> None:
    """注入依赖（占位符）"""
    _deps.update(kwargs)


async def anthropic_stream(body: dict[str, Any]) -> AsyncIterator[str]:
    """Anthropic 流式响应（占位符）"""
    # TODO Phase 2: 实现设备场景的流式响应（如有需要）
    _log.warning("[STUB] anthropic_stream called")
    yield 'data: {"type":"error","error":{"type":"not_implemented","message":"Anthropic stream not implemented in device mode"}}\n\n'


async def anthropic_stream_passthrough(body: dict[str, Any]) -> AsyncIterator[str]:
    """Anthropic 流式透传（占位符）"""
    # TODO Phase 2: 实现设备场景的流式透传（如有需要）
    _log.warning("[STUB] anthropic_stream_passthrough called")
    yield 'data: {"type":"error","error":{"type":"not_implemented","message":"Anthropic passthrough not implemented in device mode"}}\n\n'
