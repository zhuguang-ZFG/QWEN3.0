"""Release gate: prevent deployment without passing criteria."""


class ReleaseGate:
    """Validates release readiness before OTA deployment."""

    def __init__(self):
        self.criteria = {
            "tests_passing": False,
            "canary_verified": False,
            "safety_review": False,
        }

    def set_criteria(self, name: str, passed: bool):
        """Set a release criterion."""
        if name in self.criteria:
            self.criteria[name] = passed

    def is_ready(self) -> bool:
        """Check if all criteria are met."""
        return all(self.criteria.values())

    def get_status(self) -> dict:
        """Get current gate status."""
        return {
            "ready": self.is_ready(),
            "criteria": self.criteria.copy(),
        }
