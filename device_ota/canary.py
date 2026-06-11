"""Canary deployment: gradual rollout to subset of devices."""
from typing import List


class CanaryDeployment:
    """Manages canary deployment to test devices."""

    def __init__(self):
        self.canary_devices: List[str] = []
        self.deployed_version: str = ""
        self.success_count: int = 0
        self.failure_count: int = 0

    def add_canary_device(self, device_id: str):
        """Add a device to canary group."""
        if device_id not in self.canary_devices:
            self.canary_devices.append(device_id)

    def is_canary(self, device_id: str) -> bool:
        """Check if device is in canary group."""
        return device_id in self.canary_devices

    def record_success(self, device_id: str):
        """Record successful deployment."""
        if device_id in self.canary_devices:
            self.success_count += 1

    def record_failure(self, device_id: str):
        """Record failed deployment."""
        if device_id in self.canary_devices:
            self.failure_count += 1

    def is_healthy(self, threshold: float = 0.9) -> bool:
        """Check if canary is healthy (success rate >= threshold)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return False
        return (self.success_count / total) >= threshold
