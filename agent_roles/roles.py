"""Role dataclass and registry for agent roles."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Role:
    name: str
    runs_on: Literal["server", "worker"]
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    can_modify_code: bool = False


ROLES: dict[str, Role] = {
    "planner": Role(
        name="planner",
        runs_on="server",
        input_fields=("task", "context"),
        output_fields=("plan", "risks", "phases"),
    ),
    "coder": Role(
        name="coder",
        runs_on="worker",
        input_fields=("plan", "context", "files"),
        output_fields=("patch", "explanation"),
        can_modify_code=True,
    ),
    "reviewer": Role(
        name="reviewer",
        runs_on="worker",
        input_fields=("patch", "context"),
        output_fields=("findings", "severity", "suggestions"),
    ),
    "tester": Role(
        name="tester",
        runs_on="worker",
        input_fields=("patch", "test_suite"),
        output_fields=("test_results", "coverage", "regressions"),
    ),
    "security": Role(
        name="security",
        runs_on="worker",
        input_fields=("patch", "context"),
        output_fields=("vulnerabilities", "severity", "mitigations"),
    ),
    "ops": Role(
        name="ops",
        runs_on="server",
        input_fields=("patch", "environment"),
        output_fields=("deploy_plan", "rollback_steps"),
    ),
    "memory_curator": Role(
        name="memory_curator",
        runs_on="server",
        input_fields=("session_log", "existing_memories"),
        output_fields=("memories_updated", "memories_expired"),
    ),
}


def get_role(name: str) -> Role:
    """Retrieve a role by name. Raises KeyError if not found."""
    if name not in ROLES:
        raise KeyError(f"Unknown role: {name!r}. Available: {list(ROLES.keys())}")
    return ROLES[name]
