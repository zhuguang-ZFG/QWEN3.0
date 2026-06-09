"""M4: Planner — convert voice/text commands to structured TaskPlan objects.

Wraps the gateway intent parser and produces immutable TaskPlan instances
for the downstream simulator and workflow orchestrator.
"""

from __future__ import annotations

import uuid

from device_gateway.intent import parse_command

from .schemas import TaskPlan


class PlannerError(ValueError):
    """Raised when the planner cannot produce a valid plan."""


def plan_from_text(text: str, device_id: str) -> TaskPlan:
    """Parse a voice/text command and produce a structured TaskPlan.

    Raises PlannerError for empty or clearly invalid input.
    """
    stripped = (text or "").strip()
    if not stripped:
        raise PlannerError("empty command cannot be planned")

    intent = parse_command(stripped)
    capability = intent["capability"]
    params = dict(intent.get("params", {}))
    params["source"] = "planner"

    plan_id = f"plan-{uuid.uuid4().hex[:12]}"

    return TaskPlan(
        plan_id=plan_id,
        device_id=device_id,
        capability=capability,
        params=params,
    )
