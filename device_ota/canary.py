"""Canary deployment: gradual rollout to subset of devices."""

from __future__ import annotations

from pathlib import Path

from device_ota.state_store import load_state, save_section


class CanaryDeployment:
    """Manages canary deployment to test devices."""

    def __init__(self, state_path: Path | str | None = None):
        self._state_path = state_path
        self.canary_devices: list[str] = []
        self.deployed_version: str = ""
        self.success_count: int = 0
        self.failure_count: int = 0
        self.firmware: dict[str, str] = {}
        state = load_state(state_path).get("canary", {})
        if isinstance(state, dict):
            devices = state.get("canary_devices", [])
            if isinstance(devices, list):
                self.canary_devices = [str(item) for item in devices if str(item)]
            self.deployed_version = str(state.get("deployed_version") or "")
            self.success_count = int(state.get("success_count") or 0)
            self.failure_count = int(state.get("failure_count") or 0)
            firmware = state.get("firmware", {})
            if isinstance(firmware, dict):
                self.firmware = {str(k): str(v) for k, v in firmware.items()}

    def add_canary_device(self, device_id: str) -> None:
        """Add a device to canary group."""
        if device_id not in self.canary_devices:
            self.canary_devices.append(device_id)
            self._save()

    def remove_canary_device(self, device_id: str) -> bool:
        """Remove a device from canary group."""
        if device_id in self.canary_devices:
            self.canary_devices.remove(device_id)
            self._save()
            return True
        return False

    def is_canary(self, device_id: str) -> bool:
        """Check if device is in canary group."""
        return device_id in self.canary_devices

    def deploy_version(self, version: str, firmware: dict[str, str] | None = None) -> None:
        """Record the version being deployed to canary devices."""
        self.deployed_version = version
        self.firmware = firmware or {}
        self.success_count = 0
        self.failure_count = 0
        self._save()

    def record_success(self, device_id: str) -> None:
        """Record successful deployment."""
        if device_id in self.canary_devices:
            self.success_count += 1
            self._save()

    def record_failure(self, device_id: str) -> None:
        """Record failed deployment."""
        if device_id in self.canary_devices:
            self.failure_count += 1
            self._save()

    def is_healthy(self, threshold: float = 0.9) -> bool:
        """Check if canary is healthy (success rate >= threshold)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return False
        return (self.success_count / total) >= threshold

    def _save(self) -> None:
        save_section(
            self._state_path,
            "canary",
            {
                "canary_devices": self.canary_devices,
                "deployed_version": self.deployed_version,
                "success_count": self.success_count,
                "failure_count": self.failure_count,
                "firmware": self.firmware,
            },
        )
