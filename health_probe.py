"""标准化健康探针接口 — 统一探针协议和结果格式。

之前 `backend_probe_loop.py` 有自己的 `_classify_error` 与 `health_recorder.classify_failure`
重复。本模块定义标准 `ProbeResult` dataclass 和 `HealthProbe` Protocol，
消除重复，使探针逻辑可插拔。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from health_recorder import classify_failure

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """标准化探针结果。"""

    backend: str
    status: str  # healthy | empty | failed | unknown
    latency_ms: int = 0
    response_len: int = 0
    error: str | None = None
    error_code: int | None = None
    error_class: str | None = None
    timed_out: bool = False
    recorded: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """探针是否成功（healthy 状态）。"""
        return self.status == "healthy"

    def to_dict(self) -> dict[str, Any]:
        """转换为 dict（向后兼容现有 probe_backend 返回格式）。"""
        d = {
            "backend": self.backend,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }
        if self.response_len:
            d["response_len"] = self.response_len
        if self.error is not None:
            d["error"] = self.error
        if self.error_code is not None:
            d["error_code"] = self.error_code
        if self.error_class is not None:
            d["error_class"] = self.error_class
        if self.timed_out:
            d["timed_out"] = True
        if self.recorded:
            d["recorded"] = True
        return d


@runtime_checkable
class HealthProbe(Protocol):
    """健康探针协议 — 实现此接口可自定义探针类型。"""

    def probe(self, backend: str, *, ignore_cooldown: bool = False) -> ProbeResult:
        """探测后端健康状态。"""
        ...


def classify_probe_error(error_msg: str, error_code: int | None = None) -> str:
    """标准化探针错误分类 — 委托至 health_recorder.classify_failure。

    消除 backend_probe_loop._classify_error 的重复逻辑。
    """
    return classify_failure(error_code=error_code, error_text=error_msg)


def make_result(
    backend: str,
    *,
    status: str,
    latency_ms: int = 0,
    response_len: int = 0,
    error: str | None = None,
    error_code: int | None = None,
    timed_out: bool = False,
) -> ProbeResult:
    """便捷构造 ProbeResult，自动分类错误。"""
    error_class = None
    if error and status != "healthy":
        error_class = classify_probe_error(error, error_code)
    return ProbeResult(
        backend=backend,
        status=status,
        latency_ms=latency_ms,
        response_len=response_len,
        error=error,
        error_code=error_code,
        error_class=error_class,
        timed_out=timed_out,
    )
