"""
LiMa Speculative Execution — 并行投机调用 facade.

简单问题同时发 N 个快速后端，谁先返回有效响应就用谁。
实现：speculative_execution（并行执行）+ speculative_policy（策略/亲和池）。
"""

from __future__ import annotations

import budget_manager
import health_tracker
from speculative_execution import (
    is_historically_fast,
    speculative_call,
    speculative_call_async,
)
from speculative_policy import AFFINITY, classify_complexity, get_affinity_backends

__all__ = [
    "speculative_call",
    "speculative_call_async",
    "is_historically_fast",
    "classify_complexity",
    "get_affinity_backends",
    "AFFINITY",
    "health_tracker",
    "budget_manager",
]
