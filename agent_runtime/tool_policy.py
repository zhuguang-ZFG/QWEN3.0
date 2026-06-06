"""Runtime tool policy for AgentSteps.

The policy checks step allowlists and blocks dangerous authority classes without
calling any tools.
"""

from __future__ import annotations

from agent_runtime.contract import AgentStep, StepKind, StepResult, redact

READONLY_STEP_KINDS = {
    StepKind.SUMMARIZE,
    StepKind.RETRIEVE_CONTEXT,
    StepKind.RUN_TESTS,
    StepKind.REVIEW,
    StepKind.NOOP,
}

DANGEROUS_STEP_KINDS = {
    StepKind.SHELL_COMMAND,
    StepKind.HTTP_CALL,
}

DANGEROUS_TOOL_NAMES = {
    "deploy",
    "device_write",
    "exec",
    "hardware",
    "network_write",
    "rm",
    "shell",
    "shell_command",
    "sudo",
}

STEP_TOOL_ALIASES = {
    StepKind.RETRIEVE_CONTEXT: {
        "retrieve_context",
        "dev_search_docs",
        "dev_search_error",
        "dev_read_url",
        "dev_fetch_github_file",
        "dev_search_codesearch",
        "dev_summarize_sources",
    },
    StepKind.RUN_TESTS: {"run_tests", "pytest"},
}


def check_step_policy(step: AgentStep) -> StepResult | None:
    """Return None when allowed, else a blocked StepResult."""
    allowed = set(step.allowed_tools)
    kind_value = step.kind.value

    if step.kind in DANGEROUS_STEP_KINDS:
        return _blocked(step, f"dangerous step '{kind_value}' requires explicit approval")

    if any(tool in DANGEROUS_TOOL_NAMES for tool in allowed):
        return _blocked(step, "dangerous authority present in allowed_tools")

    permitted_names = STEP_TOOL_ALIASES.get(step.kind, {kind_value})
    if allowed and not (allowed & permitted_names):
        return _blocked(step, f"step kind '{kind_value}' not in allowed_tools")

    if step.kind not in READONLY_STEP_KINDS and kind_value not in allowed:
        return _blocked(step, f"step kind '{kind_value}' has no policy allow rule")

    return None


def filter_allowed_steps(
    steps: list[AgentStep],
    allowed_tools: list[str],
) -> tuple[list[AgentStep], list[AgentStep]]:
    """Split steps into allowed and blocked groups without executing tools."""
    passed: list[AgentStep] = []
    blocked: list[AgentStep] = []

    for step in steps:
        candidate = AgentStep(
            step_id=step.step_id,
            kind=step.kind,
            goal=step.goal,
            allowed_tools=list(allowed_tools),
            command=step.command,
            timeout_sec=step.timeout_sec,
            metadata=dict(step.metadata),
        )
        result = check_step_policy(candidate)
        if result is None:
            passed.append(candidate)
        else:
            blocked.append(candidate)

    return passed, blocked


def is_step_allowed(step: AgentStep) -> bool:
    return check_step_policy(step) is None


def _blocked(step: AgentStep, reason: str) -> StepResult:
    return StepResult(
        step_id=step.step_id,
        ok=False,
        blocked=True,
        blocked_reason=redact(reason),
    )
