"""Release gate: prevent deployment without passing criteria."""

from __future__ import annotations

from pathlib import Path

from device_ota.state_store import load_state, save_section


class ReleaseGate:
    """Validates release readiness before OTA deployment."""

    def __init__(self, state_path: Path | str | None = None):
        self._state_path = state_path
        self.criteria = {
            "tests_passing": False,
            "canary_verified": False,
            "safety_review": False,
        }
        gate_state = load_state(state_path).get("release_gate", {})
        criteria = gate_state.get("criteria") if isinstance(gate_state, dict) else None
        if isinstance(criteria, dict):
            for name in self.criteria:
                if isinstance(criteria.get(name), bool):
                    self.criteria[name] = criteria[name]

    def set_criteria(self, name: str, passed: bool) -> bool:
        """Set a release criterion. Returns True if the criterion exists."""
        if name in self.criteria:
            self.criteria[name] = passed
            self._save()
            return True
        return False

    def is_ready(self) -> bool:
        """Check if all criteria are met."""
        return all(self.criteria.values())

    def get_status(self) -> dict:
        """Get current gate status."""
        return {
            "ready": self.is_ready(),
            "criteria": self.criteria.copy(),
        }

    def _save(self) -> None:
        save_section(self._state_path, "release_gate", {"criteria": self.criteria.copy()})
