"""Auto-rollback monitor — orchestrates canary health checks with gradual rollout."""

from __future__ import annotations

from device_ota.canary import CanaryDeployment
from device_ota.gradual import GradualRollout


class RollbackMonitor:
    """Checks canary health and drives automatic promotion / rollback.

    When the canary deployment is healthy, the wrapped gradual rollout is
    checked for automatic promotion. After ``threshold`` consecutive unhealthy
    checks, the rollout is rolled back one stage.
    """

    def __init__(
        self,
        gradual: GradualRollout,
        canary: CanaryDeployment,
        *,
        threshold: int = 3,
    ) -> None:
        self._gradual = gradual
        self._canary = canary
        self._threshold = max(1, threshold)
        self._unhealthy_count: int = 0

    def check_and_act(self) -> str:
        """Evaluate canary health and advance or roll back the rollout.

        Returns one of: ``"healthy"``, ``"unhealthy"``, ``"promoted"``,
        ``"rolled_back"``.
        """
        if self._canary.is_healthy():
            self._unhealthy_count = 0
            if self._gradual.should_promote():
                self._gradual.promote()
                return "promoted"
            return "healthy"

        self._unhealthy_count += 1
        if self._unhealthy_count >= self._threshold:
            self._gradual.rollback()
            self._unhealthy_count = 0
            return "rolled_back"
        return "unhealthy"

    def status_dict(self) -> dict[str, object]:
        """Return a JSON-serializable snapshot of the monitor state."""
        return {
            "unhealthy_count": self._unhealthy_count,
            "threshold": self._threshold,
            "canary_healthy": self._canary.is_healthy(),
            "stage_should_promote": self._gradual.should_promote(),
            "stage_should_rollback": self._gradual.should_rollback(),
        }
