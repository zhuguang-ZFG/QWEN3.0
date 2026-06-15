"""Canary deployment: gradual rollout to subset of devices."""


class CanaryDeployment:
    """Manages canary deployment to test devices."""

    def __init__(self):
        self.canary_devices: list[str] = []
        self.deployed_version: str = ""
        self.success_count: int = 0
        self.failure_count: int = 0

    def add_canary_device(self, device_id: str) -> None:
        """Add a device to canary group."""
        if device_id not in self.canary_devices:
            self.canary_devices.append(device_id)

    def remove_canary_device(self, device_id: str) -> bool:
        """Remove a device from canary group."""
        if device_id in self.canary_devices:
            self.canary_devices.remove(device_id)
            return True
        return False

    def is_canary(self, device_id: str) -> bool:
        """Check if device is in canary group."""
        return device_id in self.canary_devices

    def deploy_version(self, version: str) -> None:
        """Record the version being deployed to canary devices."""
        self.deployed_version = version
        self.success_count = 0
        self.failure_count = 0

    def record_success(self, device_id: str) -> None:
        """Record successful deployment."""
        if device_id in self.canary_devices:
            self.success_count += 1

    def record_failure(self, device_id: str) -> None:
        """Record failed deployment."""
        if device_id in self.canary_devices:
            self.failure_count += 1

    def is_healthy(self, threshold: float = 0.9) -> bool:
        """Check if canary is healthy (success rate >= threshold)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return False
        return (self.success_count / total) >= threshold
