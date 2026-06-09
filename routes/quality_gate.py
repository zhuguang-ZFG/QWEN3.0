"""
Quality gate - Simplified stub for strategic pivot.

原 quality_gate.py 已删除（编码助手专属质量门控）。
此文件提供最小占位符，避免大量修改 routes/chat_fallback.py 和 routes/chat_handler.py。
Phase 2 将重构为设备场景专用的质量检查。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)

# State placeholder
_backend_enabled: dict[str, bool] = {}


def inject_state(backend_enabled: dict[str, bool]) -> None:
    """注入后端状态（占位符）"""
    global _backend_enabled
    _backend_enabled = backend_enabled


def quality_check(response_text: str, query: str) -> bool:
    """质量检查（占位符 - 始终通过）"""
    # TODO Phase 2: 实现设备场景的质量检查
    return True


def default_route(model: str, backend_enabled: dict[str, bool]) -> str:
    """默认路由选择（占位符）"""
    # TODO Phase 2: 实现设备场景的路由选择
    for backend, enabled in backend_enabled.items():
        if enabled:
            return backend
    return "openrouter"


def get_same_tier_backends(backend: str, backend_enabled: dict[str, bool]) -> list[str]:
    """获取同级后端（占位符）"""
    # TODO Phase 2: 实现设备场景的后端分层
    return [b for b, enabled in backend_enabled.items() if enabled and b != backend]


def get_upgrade_chain(backend: str, backend_enabled: dict[str, bool]) -> list[str]:
    """获取升级链（占位符）"""
    # TODO Phase 2: 实现设备场景的升级策略
    return []


def honest_failure_response(
    chat_id: str, query: str, backend: str, duration_ms: int, fmt: str = "openai"
) -> JSONResponse:
    """诚实的失败响应（占位符）"""
    # TODO Phase 2: 实现设备场景的失败处理
    error_msg = f"Request failed on backend {backend}"
    if fmt == "anthropic":
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "error": {
                    "type": "internal_error",
                    "message": error_msg,
                },
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": error_msg,
                "type": "internal_error",
            }
        },
    )


async def try_backend(
    backend: str,
    chat_req: Any,
    fmt: str,
    client_ip: str,
    ide_source: str,
    sys_prompt_preview: str,
    request_headers: dict[str, str],
    call_route: Any,
    maybe_await: Any,
) -> tuple[str | None, int]:
    """尝试调用后端（占位符）"""
    # TODO Phase 2: 实现设备场景的后端调用
    _log.warning("[STUB] try_backend called with backend=%s", backend)
    return None, 0
