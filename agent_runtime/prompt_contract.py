"""LiMa Task Prompt Contract v0.1 — parse, validate, migrate, render."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_OUTPUT = (
    "Return needs_review with summary JSON: changed_files, tests_run, "
    "remaining_risks, review_status."
)

_MAX_CONTEXT = 2000
_MAX_TASK = 1000
_MAX_CONSTRAINT_ITEM = 500
_MAX_CONSTRAINTS = 20
_MAX_VERIFY_ITEM = 500
_MAX_VERIFY = 10
_MAX_OUTPUT = 1000


@dataclass
class PromptContract:
    context: str = ""
    task: str = ""
    constraints: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=list)
    output: str = ""


def _check_len(value: str, max_len: int, label: str) -> None:
    if len(value) > max_len:
        raise ValueError(f"{label} exceeds max length {max_len}")


def _check_str_list(
    items: object,
    *,
    label: str,
    item_max: int,
    count_max: int,
) -> list[str]:
    if not isinstance(items, list):
        raise ValueError(f"{label} must be a list")
    if len(items) > count_max:
        raise ValueError(f"{label} exceeds max count {count_max}")
    out: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, str):
            raise ValueError(f"{label}[{idx}] must be a string")
        _check_len(item, item_max, f"{label}[{idx}]")
        out.append(item)
    return out


def parse_prompt_contract(raw: dict | None) -> PromptContract:
    """Validate explicit contract fields; raises ValueError on invalid input."""
    if not raw:
        return PromptContract()
    if not isinstance(raw, dict):
        raise ValueError("prompt_contract must be an object")

    context = raw.get("context", "")
    task = raw.get("task", "")
    output = raw.get("output", "")
    if not isinstance(context, str):
        raise ValueError("prompt_contract.context must be a string")
    if not isinstance(task, str):
        raise ValueError("prompt_contract.task must be a string")
    if not isinstance(output, str):
        raise ValueError("prompt_contract.output must be a string")

    _check_len(context, _MAX_CONTEXT, "prompt_contract.context")
    _check_len(task, _MAX_TASK, "prompt_contract.task")
    _check_len(output, _MAX_OUTPUT, "prompt_contract.output")

    constraints = _check_str_list(
        raw.get("constraints", []),
        label="prompt_contract.constraints",
        item_max=_MAX_CONSTRAINT_ITEM,
        count_max=_MAX_CONSTRAINTS,
    )
    verify = _check_str_list(
        raw.get("verify", []),
        label="prompt_contract.verify",
        item_max=_MAX_VERIFY_ITEM,
        count_max=_MAX_VERIFY,
    )
    return PromptContract(
        context=context,
        task=task,
        constraints=constraints,
        verify=verify,
        output=output,
    )


def output_hint_for_mode(mode: str) -> str:
    if mode == "plan":
        return (
            "Return needs_review with plan artifact paths and summary JSON: "
            "changed_files, tests_run, remaining_risks, review_status."
        )
    if mode == "review":
        return (
            "Return needs_review with diff review findings and summary JSON: "
            "changed_files, tests_run, remaining_risks, review_status."
        )
    if mode == "test":
        return (
            "Return succeeded or failed with test evidence and summary JSON: "
            "changed_files, tests_run, remaining_risks, review_status."
        )
    return DEFAULT_OUTPUT


def migrate_from_legacy(
    goal: str,
    constraints: list[str] | None = None,
    test_commands: list[str] | None = None,
    mode: str = "patch",
) -> PromptContract:
    task = (goal or "").strip()
    if not task:
        raise ValueError("goal must not be empty")
    return PromptContract(
        context="",
        task=task,
        constraints=list(constraints or []),
        verify=list(test_commands or []),
        output=output_hint_for_mode(mode),
    )


def resolve_prompt_contract(
    *,
    goal: str,
    constraints: list[str] | None = None,
    test_commands: list[str] | None = None,
    mode: str = "patch",
    prompt_contract: dict | None = None,
) -> PromptContract:
    migrated = migrate_from_legacy(goal, constraints, test_commands, mode)
    if not prompt_contract:
        return migrated

    parsed = parse_prompt_contract(prompt_contract)
    return PromptContract(
        context=parsed.context if "context" in prompt_contract else migrated.context,
        task=parsed.task if parsed.task else migrated.task,
        constraints=(
            parsed.constraints
            if "constraints" in prompt_contract
            else migrated.constraints
        ),
        verify=parsed.verify if "verify" in prompt_contract else migrated.verify,
        output=parsed.output if parsed.output else migrated.output,
    )


def contract_to_dict(contract: PromptContract) -> dict[str, object]:
    return {
        "context": contract.context,
        "task": contract.task,
        "constraints": list(contract.constraints),
        "verify": list(contract.verify),
        "output": contract.output,
    }


def render_prompt_contract(contract: PromptContract) -> str:
    context = contract.context.strip() or "(none)"
    task = contract.task.strip() or "(none)"
    output = contract.output.strip() or DEFAULT_OUTPUT

    lines = ["## Context", context, "", "## Task", task, "", "## Constraints"]
    if contract.constraints:
        lines.extend(f"- {item}" for item in contract.constraints)
    else:
        lines.append("- (none)")

    lines.extend(["", "## Verify"])
    if contract.verify:
        lines.extend(f"- {item}" for item in contract.verify)
    else:
        lines.append("- (none)")

    lines.extend(["", "## Output", output])
    return "\n".join(lines)
