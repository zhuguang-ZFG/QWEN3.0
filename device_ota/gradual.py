"""Gradual rollout engine — auto-progress through 5% → 20% → 50% → 100%."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from device_ota.state_store import load_state, save_section


class GradualRollout:
    """Manages a staged rollout to a fleet of devices.

    Devices are selected deterministically per stage using a stable hash so the
    same fleet/version always yields the same subsets. Stage counters and the
    current stage index are persisted to the shared OTA state file.
    """

    STAGES: list[tuple[str, float]] = [
        ("canary", 0.05),
        ("early", 0.20),
        ("mid", 0.50),
        ("full", 1.00),
    ]

    def __init__(
        self,
        state_path: Path | str | None = None,
        *,
        promote_threshold: float = 0.9,
        rollback_threshold: float = 0.15,
        min_samples: int = 5,
    ) -> None:
        self._state_path = state_path
        self._promote_threshold = promote_threshold
        self._rollback_threshold = rollback_threshold
        self._min_samples = min_samples

        self.version: str = ""
        self.all_devices: list[str] = []
        self.firmware: dict[str, str] = {}
        self.stage_index: int = 0
        self.stage_success: int = 0
        self.stage_failure: int = 0

        self._load()

    def start(self, version: str, devices: list[str], firmware: dict[str, str]) -> None:
        """Begin a new gradual rollout at the first stage."""
        self.version = version
        self.all_devices = sorted({str(d) for d in devices if str(d)})
        self.firmware = {str(k): str(v) for k, v in (firmware or {}).items()}
        self.stage_index = 0
        self.stage_success = 0
        self.stage_failure = 0
        self._save()

    def select_devices_for_stage(
        self,
        devices: list[str] | None = None,
        version: str | None = None,
    ) -> list[str]:
        """Return the stable subset of devices included in the current stage."""
        devices = self.all_devices if devices is None else sorted({str(d) for d in devices if str(d)})
        version = self.version if version is None else version
        if not devices or not version:
            return []

        stage_name, ratio = self.STAGES[self.stage_index]
        count = max(1, math.ceil(len(devices) * ratio))

        def sort_key(device_id: str) -> str:
            payload = f"{version}|{stage_name}|{device_id}"
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()

        ranked = sorted(devices, key=sort_key)
        return ranked[:count]

    def is_device_selected(self, device_id: str) -> bool:
        """Check whether a device is part of the current stage's rollout subset."""
        return device_id in self.select_devices_for_stage()

    def should_promote(self) -> bool:
        """Return True when the current stage has enough healthy samples to advance."""
        total = self.stage_success + self.stage_failure
        if total == 0 or total < self._min_samples:
            return False
        return (self.stage_success / total) >= self._promote_threshold

    def should_rollback(self) -> bool:
        """Return True when the current stage failure rate is too high."""
        total = self.stage_success + self.stage_failure
        if total == 0 or total < self._min_samples:
            return False
        return (self.stage_failure / total) > self._rollback_threshold

    def promote(self) -> bool:
        """Advance to the next rollout stage and reset counters."""
        if self.stage_index >= len(self.STAGES) - 1:
            return False
        self.stage_index += 1
        self.stage_success = 0
        self.stage_failure = 0
        self._save()
        return True

    def rollback(self) -> bool:
        """Move one stage back and reset counters."""
        if self.stage_index <= 0:
            self.stage_success = 0
            self.stage_failure = 0
            self._save()
            return False
        self.stage_index -= 1
        self.stage_success = 0
        self.stage_failure = 0
        self._save()
        return True

    def record_success(self, device_id: str | None = None) -> None:
        """Record a successful deployment in the current stage."""
        self.stage_success += 1
        self._save()

    def record_failure(self, device_id: str | None = None) -> None:
        """Record a failed deployment in the current stage."""
        self.stage_failure += 1
        self._save()

    def status_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the rollout state."""
        stage_name, ratio = self.STAGES[self.stage_index]
        total = self.stage_success + self.stage_failure
        success_rate = self.stage_success / total if total else None
        failure_rate = self.stage_failure / total if total else None
        return {
            "version": self.version,
            "stage_index": self.stage_index,
            "stage": stage_name,
            "ratio": ratio,
            "total_devices": len(self.all_devices),
            "selected_devices": self.select_devices_for_stage(),
            "stage_success": self.stage_success,
            "stage_failure": self.stage_failure,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "should_promote": self.should_promote(),
            "should_rollback": self.should_rollback(),
        }

    def _load(self) -> None:
        state = load_state(self._state_path).get("gradual", {})
        if not isinstance(state, dict):
            return
        self.version = str(state.get("version") or "")
        devices = state.get("all_devices", [])
        if isinstance(devices, list):
            self.all_devices = [str(item) for item in devices if str(item)]
        firmware = state.get("firmware", {})
        if isinstance(firmware, dict):
            self.firmware = {str(k): str(v) for k, v in firmware.items()}
        self.stage_index = max(0, min(int(state.get("stage_index") or 0), len(self.STAGES) - 1))
        self.stage_success = int(state.get("stage_success") or 0)
        self.stage_failure = int(state.get("stage_failure") or 0)

    def _save(self) -> None:
        save_section(
            self._state_path,
            "gradual",
            {
                "version": self.version,
                "all_devices": self.all_devices,
                "firmware": self.firmware,
                "stage_index": self.stage_index,
                "stage_success": self.stage_success,
                "stage_failure": self.stage_failure,
            },
        )
