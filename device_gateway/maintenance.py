"""Predictive maintenance heuristics based on the device task ledger."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from device_ledger.store import ledger_store

_log = logging.getLogger(__name__)

_FAILURE_PHASES = frozenset({"failed", "error"})
_SUCCESS_PHASES = frozenset({"done", "completed", "success"})


class PredictiveMaintenance:
    """Trend analysis and maintenance recommendations for a device."""

    def analyze_trend(self, device_id: str, days: int = 7) -> dict[str, Any]:
        """Return trend summary and recommended actions for the device."""
        try:
            events = ledger_store.events_for_device(device_id)
        except Exception:
            _log.warning("ledger_store.events_for_device failed for %s", device_id, exc_info=True)
            events = []

        cutoff = _days_ago_iso(days)
        recent = [e for e in events if (e.created_at or "") >= cutoff]
        terminals = [e for e in recent if e.event_type == "task_terminal"]

        failures = self._count_phases(terminals, _FAILURE_PHASES)
        successes = self._count_phases(terminals, _SUCCESS_PHASES)
        total = len(terminals)

        failure_rate = failures / total if total else 0.0
        trend = self._trend(failure_rate, recent)
        predicted_failures = self._predicted_failures(failure_rate, trend, total)
        actions = self._recommended_actions(device_id, failure_rate, trend, recent)
        next_maintenance = self._next_maintenance_date(trend, recent)

        return {
            "trend": trend,
            "predicted_failures": predicted_failures,
            "recommended_actions": actions,
            "next_maintenance": next_maintenance,
            "window_days": days,
            "total_events": len(recent),
            "terminal_events": total,
            "failure_count": failures,
            "success_count": successes,
        }

    def _count_phases(self, terminals: list[Any], phases: frozenset[str]) -> int:
        count = 0
        for event in terminals:
            terminal_event = event.payload.get("terminal_event", {})
            phase = ""
            if isinstance(terminal_event, dict):
                phase = str(terminal_event.get("phase", "")).lower()
            if phase in phases:
                count += 1
        return count

    def _trend(self, failure_rate: float, recent: list[Any]) -> str:
        if failure_rate >= 0.5:
            return "critical"
        if failure_rate >= 0.25:
            return "degrading"
        if recent and failure_rate == 0.0:
            return "improving"
        return "stable"

    def _predicted_failures(self, failure_rate: float, trend: str, total: int) -> int:
        if total == 0:
            return 0
        multiplier = {"critical": 1.2, "degrading": 1.0, "stable": 0.8, "improving": 0.5}.get(
            trend, 1.0
        )
        return max(0, int(round(failure_rate * total * multiplier)))

    def _recommended_actions(
        self,
        device_id: str,
        failure_rate: float,
        trend: str,
        recent: list[Any],
    ) -> list[str]:
        actions: list[str] = []
        if trend == "critical":
            actions.append(f"立即检修设备 {device_id}：最近失败率 {failure_rate:.0%}")
        elif trend == "degrading":
            actions.append(f"安排预防性维护：设备 {device_id} 失败率上升")
        if self._has_repeated_error(recent, "motion_timeout"):
            actions.append("检查机械传动与电机状态（多次运动超时）")
        if self._has_repeated_error(recent, "pen"):
            actions.append("检查笔/墨耗材与书写机构")
        if not actions:
            actions.append("当前状态正常，继续保持监控")
        return actions

    def _has_repeated_error(self, recent: list[Any], keyword: str, threshold: int = 2) -> bool:
        count = 0
        for event in recent:
            if event.event_type != "task_terminal":
                continue
            terminal_event = event.payload.get("terminal_event", {})
            error = ""
            if isinstance(terminal_event, dict):
                error = str(terminal_event.get("error", "") or terminal_event.get("error_code", ""))
            if keyword in error.lower():
                count += 1
        return count >= threshold

    def _next_maintenance_date(self, trend: str, recent: list[Any]) -> str | None:
        if trend in {"critical", "degrading"}:
            return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        if trend == "stable" and recent:
            return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
        return None


def _days_ago_iso(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    return dt.isoformat().replace("+00:00", "Z")
