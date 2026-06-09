"""Recovery decisions for device motion failures."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Literal

_log = logging.getLogger(__name__)

RecoveryActionName = Literal["retry", "home", "stop", "none"]


@dataclass(frozen=True)
class RecoveryAction:
    action: RecoveryActionName
    max_retries: int
    cooldown_ms: int
    explanation_zh: str


_ACTIONS: dict[str, RecoveryAction] = {
    "E_MISSING_PATH": RecoveryAction("retry", 3, 2000, "设备未收到路径数据，等待后重试下发任务。"),
    "E_LIMIT": RecoveryAction("retry", 1, 500, "触发限位保护，短暂冷却后允许一次重试。"),
    "E_NOT_HOMED": RecoveryAction("home", 0, 0, "设备尚未回零，需要先执行回零流程。"),
    "E_UART_TIMEOUT": RecoveryAction("retry", 2, 1000, "串口通信超时，等待链路恢复后重试。"),
    "E_ESTOP": RecoveryAction("stop", 0, 0, "急停已触发，立即停止并等待人工确认。"),
}

_UNKNOWN_ACTION = RecoveryAction("stop", 0, 0, "未知错误，停止任务并等待人工检查。")


def recovery_action(error_code: str) -> RecoveryAction:
    code = str(error_code or "").strip().upper()
    action = _ACTIONS.get(code)
    if action is None:
        _log.warning("unknown device recovery error_code=%s", code or "<empty>")
        return _UNKNOWN_ACTION
    return action


def should_retry(error_code: str, attempt: int) -> bool:
    action = recovery_action(error_code)
    if action.action != "retry":
        return False
    return 0 <= attempt < action.max_retries
