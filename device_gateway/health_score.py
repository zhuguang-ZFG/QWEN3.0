"""Device health scoring based on live sessions, task ledger, firmware and self-checks."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.firmware_matrix import COMPATIBILITY_MATRIX
from device_gateway.sessions import registry
from device_ledger.store import ledger_store

_log = logging.getLogger(__name__)

SUCCESS_PHASES = frozenset({"done", "completed", "success"})
FAILURE_PHASES = frozenset({"failed", "error", "cancelled"})

KNOWN_FIRMWARE_SCORES: dict[str, int] = {
    "v1.3.0": 100,
    "v1.2.0": 80,
    "v1.1.0": 60,
    "v1.0.0": 40,
}

HARDWARE_RESULT_SCORES: dict[str, int] = {
    "pass": 100,
    "warning": 60,
    "fail": 20,
}


class DeviceHealthScore:
    """Compute a multi-dimensional health score for a single device."""

    DIMENSIONS = ["connectivity", "task_success", "response_time", "firmware", "hardware"]

    def compute(self, device_id: str) -> dict[str, Any]:
        """Return total score, per-dimension breakdown and aggregated status."""
        dimensions: dict[str, int] = {
            "connectivity": self._connectivity_score(device_id),
            "task_success": self._task_success_score(device_id),
            "response_time": self._response_time_score(device_id),
            "firmware": self._firmware_score(device_id),
            "hardware": self._hardware_score(device_id),
        }
        total = int(sum(dimensions.values()) / len(dimensions))
        return {
            "total": total,
            "dimensions": dimensions,
            "status": self._status(total),
        }

    def _connectivity_score(self, device_id: str) -> int:
        return 100 if registry.get(device_id) is not None else 0

    def _task_success_score(self, device_id: str) -> int:
        try:
            events = ledger_store.events_for_device(device_id)
        except Exception:
            _log.warning("ledger_store.events_for_device failed for %s", device_id, exc_info=True)
            return 50

        terminal = [e for e in events if e.event_type == "task_terminal"][-30:]
        if not terminal:
            return 50

        successes = sum(
            1 for e in terminal if self._terminal_phase(e.payload.get("terminal_event", {})) in SUCCESS_PHASES
        )
        return int(100 * successes / len(terminal))

    def _terminal_phase(self, terminal_event: Any) -> str:
        if isinstance(terminal_event, dict):
            return str(terminal_event.get("phase", "")).lower()
        return ""

    def _response_time_score(self, _device_id: str) -> int:
        # ponytail: placeholder until heartbeat RTT telemetry is available.
        return 80

    def _parse_semver(self, version: str) -> tuple[int, ...]:
        """Convert a 'v1.2.3' string into a numeric tuple for semantic comparison."""
        parts = version.lstrip("v").split(".")
        try:
            return tuple(int(p) for p in parts if p.isdigit())
        except ValueError:
            return (0,)

    def _firmware_score(self, device_id: str) -> int:
        session = registry.get(device_id)
        version = session.fw_rev if session else self._device_firmware_version(device_id)
        if not version:
            return 50
        if version in KNOWN_FIRMWARE_SCORES:
            return KNOWN_FIRMWARE_SCORES[version]
        known = sorted(KNOWN_FIRMWARE_SCORES.keys(), key=self._parse_semver)
        parsed = self._parse_semver(version)
        if parsed > self._parse_semver(known[-1]):
            return 100
        if parsed < self._parse_semver(known[0]):
            return 30
        return 50

    def _device_firmware_version(self, device_id: str) -> str:
        try:
            from device_logic.db import connect

            with connect() as conn:
                row = conn.execute("SELECT firmware_ver FROM v2_device WHERE id=?", (device_id,)).fetchone()
            return str(row["firmware_ver"]) if row and row["firmware_ver"] else ""
        except Exception:
            _log.warning("failed to read firmware version for %s", device_id, exc_info=True)
            return ""

    def _hardware_score(self, device_id: str) -> int:
        try:
            from device_logic.db import connect

            with connect() as conn:
                row = conn.execute(
                    "SELECT result FROM v2_self_check_event WHERE device_id=? ORDER BY created_at DESC LIMIT 1",
                    (device_id,),
                ).fetchone()
        except Exception:
            _log.warning("failed to read self-check result for %s", device_id, exc_info=True)
            return 50

        if row is None:
            return 50
        result = str(row["result"]).lower() if row["result"] else ""
        return HARDWARE_RESULT_SCORES.get(result, 50)

    def _status(self, total: int) -> str:
        if total >= 90:
            return "excellent"
        if total >= 75:
            return "good"
        if total >= 50:
            return "warning"
        return "critical"


def _latest_firmware() -> str:
    """Return the newest known firmware version."""
    return max(COMPATIBILITY_MATRIX.keys()) if COMPATIBILITY_MATRIX else "v1.3.0"
