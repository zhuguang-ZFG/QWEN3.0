"""Deterministic planner with static keyword-based step decomposition.

No LLM calls are made here. The planner maps goal text to a fixed sequence of
safe AgentSteps and only emits shell proposals when explicitly allowed.
"""

from __future__ import annotations

from agent_runtime.contract import AgentStep, AgentTask, StepKind


def plan_task(task: AgentTask) -> AgentTask:
    """Fill task.steps deterministically from task.goal keywords."""
    task.steps = _compile_steps(
        task.goal,
        set(task.allowed_tools),
        task.authority_budget,
    )
    return task


def _compile_steps(goal: str, allowed: set[str], budget: int) -> list[AgentStep]:
    if not goal or not goal.strip():
        return [
            AgentStep(
                step_id="step-1",
                kind=StepKind.NOOP,
                goal="empty goal - nothing to do",
            )
        ]

    lower = goal.lower()
    steps: list[AgentStep] = []

    if any(word in lower for word in ("search", "context", "retrieve", "find", "look up")):
        steps.append(AgentStep(
            step_id=_next_step_id(steps),
            kind=StepKind.RETRIEVE_CONTEXT,
            goal="Retrieve relevant context from codebase or memory",
            allowed_tools=sorted(allowed),
        ))

    if any(word in lower for word in ("test", "verify", "check", "validate")):
        steps.append(AgentStep(
            step_id=_next_step_id(steps),
            kind=StepKind.RUN_TESTS,
            goal="Propose test command and collect dry-run evidence",
            command="pytest --tb=short" if "pytest" in allowed else "",
            allowed_tools=sorted(allowed),
        ))

    if any(word in lower for word in ("review", "audit", "inspect", "analyze")):
        steps.append(AgentStep(
            step_id=_next_step_id(steps),
            kind=StepKind.REVIEW,
            goal="Review code changes and produce checklist",
            allowed_tools=sorted(allowed),
        ))

    if "shell" in allowed and any(word in lower for word in ("deploy", "build", "run", "execute")):
        steps.append(AgentStep(
            step_id=_next_step_id(steps),
            kind=StepKind.SHELL_COMMAND,
            goal=f"Propose shell command for: {goal[:100]}",
            command=goal[:200],
            allowed_tools=sorted(allowed),
        ))

    budget = max(1, int(budget))
    if len(steps) > budget:
        steps = steps[:budget]

    if not steps:
        steps.append(AgentStep(
            step_id="step-1",
            kind=StepKind.SUMMARIZE,
            goal=f"Summarize: {goal[:200]}",
            allowed_tools=sorted(allowed),
        ))

    return steps


def _next_step_id(steps: list[AgentStep]) -> str:
    return f"step-{len(steps) + 1}"
