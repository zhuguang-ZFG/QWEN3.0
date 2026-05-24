"""Tests for M17 agent task runtime."""

from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentStep,
    AgentTask,
    StepKind,
    StepResult,
)
from agent_runtime.events import (
    emit_step_result,
    emit_step_start,
    emit_task_done,
    emit_task_start,
    emit_warning,
    make_audit_ref,
)
from agent_runtime.executor import AgentRuntime, RuntimeHooks
from agent_runtime.planner import plan_task
from agent_runtime.tool_policy import (
    check_step_policy,
    filter_allowed_steps,
    is_step_allowed,
)


def test_agent_task_to_dict_redacts_secrets():
    task = AgentTask(
        task_id="task-1",
        goal="fix bug with api_key=sk-secret-value",
        workspace="/home/user/project",
        allowed_tools=["dev_search_docs"],
        audit_refs=["Bearer token"],
    )

    data = task.to_dict()

    assert data["goal"] == "[REDACTED]"
    assert data["workspace"] == "/home/user/project"
    assert data["audit_refs"] == ["[REDACTED]"]


def test_agent_task_from_dict_round_trip_and_defaults():
    task = AgentTask.from_dict({
        "task_id": "task-1",
        "goal": "review",
        "status": "not-real",
        "steps": [{"step_id": "s1", "kind": "review", "metadata": {"safe": "ok"}}],
    })

    assert task.status is AgentRunStatus.PENDING
    assert task.steps[0].kind is StepKind.REVIEW
    assert task.steps[0].metadata["safe"] == "ok"


def test_agent_step_to_dict_redacts_command_and_metadata():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.RUN_TESTS,
        command="pytest --token=sk-secret",
        metadata={"api_key": "sk-secret", "safe": "ok"},
    )

    data = step.to_dict()

    assert data["command"] == "[REDACTED]"
    assert data["metadata"]["[REDACTED]"] == "[REDACTED]"
    assert data["metadata"]["safe"] == "ok"


def test_step_result_to_dict_and_from_dict():
    result = StepResult(
        step_id="s1",
        ok=True,
        output="all good",
        evidence=["test passed"],
        duration_ms=150.0,
    )

    data = result.to_dict()
    restored = StepResult.from_dict(data)

    assert data["ok"] is True
    assert restored.duration_ms == 150.0
    assert restored.evidence == ["test passed"]


def test_agent_run_result_ok_and_redacts_audit_refs():
    result = AgentRunResult(
        task_id="t1",
        status=AgentRunStatus.COMPLETED,
        audit_refs=["token=secret"],
    )
    failed = AgentRunResult(task_id="t2", status=AgentRunStatus.FAILED)

    assert result.ok is True
    assert result.to_dict()["audit_refs"] == ["[REDACTED]"]
    assert failed.ok is False


def test_agent_run_result_from_dict_defaults_failed_status():
    result = AgentRunResult.from_dict({"task_id": "t1", "status": "not-real"})

    assert result.status is AgentRunStatus.FAILED


def test_step_kind_enum():
    assert StepKind.SUMMARIZE == "summarize"
    assert StepKind.SHELL_COMMAND == "shell_command"
    assert StepKind.RETRIEVE_CONTEXT == "retrieve_context"


def test_plan_empty_goal():
    task = AgentTask(task_id="t1", goal="")
    plan_task(task)

    assert len(task.steps) == 1
    assert task.steps[0].kind == StepKind.NOOP


def test_plan_test_goal():
    task = AgentTask(task_id="t1", goal="run tests and verify everything passes")
    plan_task(task)

    kinds = {step.kind for step in task.steps}

    assert StepKind.RUN_TESTS in kinds


def test_plan_review_goal():
    task = AgentTask(task_id="t1", goal="review the code changes for security")
    plan_task(task)

    kinds = {step.kind for step in task.steps}

    assert StepKind.REVIEW in kinds


def test_plan_search_goal():
    task = AgentTask(task_id="t1", goal="search for routing engine context")
    plan_task(task)

    kinds = {step.kind for step in task.steps}

    assert StepKind.RETRIEVE_CONTEXT in kinds


def test_plan_respects_budget():
    task = AgentTask(
        task_id="t1",
        goal="test review search context verify",
        authority_budget=2,
    )
    plan_task(task)

    assert len(task.steps) <= 2


def test_plan_shell_only_when_allowed():
    task = AgentTask(task_id="t1", goal="deploy to production", allowed_tools=[])
    plan_task(task)
    assert StepKind.SHELL_COMMAND not in {step.kind for step in task.steps}

    allowed = AgentTask(
        task_id="t2",
        goal="deploy to production",
        allowed_tools=["shell"],
    )
    plan_task(allowed)
    assert StepKind.SHELL_COMMAND in {step.kind for step in allowed.steps}


def test_runtime_default_dry_run():
    runtime = AgentRuntime()
    task = AgentTask(task_id="t1", goal="test the routing engine")

    result = runtime.run(task)

    assert result.ok is True
    assert result.status == AgentRunStatus.COMPLETED
    assert len(result.steps) >= 1
    assert len(result.audit_refs) >= 1


def test_runtime_applies_policy_before_handlers():
    runtime = AgentRuntime(dry_run=True)
    step = AgentStep(
        step_id="s1",
        kind=StepKind.HTTP_CALL,
        goal="call external URL",
    )

    result = runtime.run_step(step)

    assert result.blocked is True
    assert "http" in result.blocked_reason.lower()


def test_runtime_shell_blocked_in_dry_run():
    runtime = AgentRuntime(dry_run=True)
    task = AgentTask(
        task_id="t1",
        goal="deploy to production",
        allowed_tools=["shell"],
    )

    result = runtime.run(task)
    blocked_steps = [step for step in result.steps if step.blocked]

    assert len(blocked_steps) >= 1
    assert "shell" in blocked_steps[0].blocked_reason.lower()


def test_runtime_review_produces_checklist():
    runtime = AgentRuntime()
    task = AgentTask(task_id="t1", goal="review the code")

    result = runtime.run(task)
    review_steps = [step for step in task.steps if step.kind == StepKind.REVIEW]

    assert len(review_steps) >= 1
    assert result.ok is True


def test_runtime_retrieve_context_with_hook_redacts_output():
    def fake_retrieve(query: str) -> str:
        return f"Found token=sk-secret for '{query}'"

    runtime = AgentRuntime(hooks=RuntimeHooks(on_retrieve_context=fake_retrieve))
    task = AgentTask(task_id="t1", goal="search for routing context")

    result = runtime.run(task)

    assert result.status == AgentRunStatus.COMPLETED
    assert result.steps[0].output == "[REDACTED]"


def test_runtime_retrieve_context_hook_error_redacts():
    def bad_retrieve(query: str) -> str:
        raise RuntimeError("index not available token=secret")

    runtime = AgentRuntime(hooks=RuntimeHooks(on_retrieve_context=bad_retrieve))
    task = AgentTask(task_id="t1", goal="search for routing context")

    result = runtime.run(task)

    assert result.status == AgentRunStatus.FAILED
    assert result.steps[0].error == "[REDACTED]"


def test_runtime_audit_refs_do_not_leak_secrets():
    runtime = AgentRuntime()
    task = AgentTask(task_id="token=secret", goal="summarize")

    result = runtime.run(task)

    assert all("token=secret" not in ref for ref in result.audit_refs)


def test_events_no_secret_in_output():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SUMMARIZE,
        goal="use token=sk-secret-key",
    )

    sse = emit_step_start(step)

    assert "sk-secret-key" not in sse
    assert "token=" not in sse


def test_events_warning_fallback_redacts_secret():
    sse = emit_warning("rate limit token=sk-secret", task_id="t1")

    assert "warning" in sse.lower()
    assert "sk-secret" not in sse
    assert "token=" not in sse


def test_events_produce_output():
    sse = emit_task_start("task-1")
    done = emit_task_done(
        AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED),
        audit_ref="audit-abc",
    )

    assert "task_start" in sse or "task-1" in sse
    assert "done" in done.lower() or "t1" in done


def test_emit_step_result_redacts_block_reason():
    sse = emit_step_result(StepResult(
        step_id="s1",
        ok=False,
        blocked=True,
        blocked_reason="token=secret",
    ))

    assert "token=secret" not in sse


def test_make_audit_ref_redacts_task_id():
    ref = make_audit_ref("token=secret")

    assert ref.startswith("audit-[REDACTED]-")
    assert "token=secret" not in ref


def test_check_step_policy_allows_readonly():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SUMMARIZE,
        allowed_tools=["summarize", "retrieve_context"],
    )

    assert check_step_policy(step) is None


def test_check_step_policy_allows_pytest_alias_for_run_tests():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.RUN_TESTS,
        allowed_tools=["pytest"],
    )

    assert check_step_policy(step) is None


def test_check_step_policy_blocks_not_allowed():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.RUN_TESTS,
        allowed_tools=["summarize"],
    )

    result = check_step_policy(step)

    assert result is not None
    assert result.blocked is True
    assert "not in allowed_tools" in result.blocked_reason


def test_check_step_policy_blocks_shell_and_http():
    for kind in (StepKind.SHELL_COMMAND, StepKind.HTTP_CALL):
        result = check_step_policy(AgentStep(step_id="s1", kind=kind))
        assert result is not None
        assert result.blocked is True


def test_filter_allowed_steps_does_not_mutate_original_steps():
    steps = [
        AgentStep(step_id="s1", kind=StepKind.SUMMARIZE),
        AgentStep(step_id="s2", kind=StepKind.SHELL_COMMAND),
    ]

    passed, blocked = filter_allowed_steps(steps, ["summarize"])

    assert len(passed) == 1
    assert len(blocked) == 1
    assert steps[0].allowed_tools == []


def test_is_step_allowed():
    assert is_step_allowed(AgentStep(
        step_id="s1",
        kind=StepKind.SUMMARIZE,
        allowed_tools=["summarize"],
    )) is True
    assert is_step_allowed(AgentStep(
        step_id="s2",
        kind=StepKind.SHELL_COMMAND,
        allowed_tools=[],
    )) is False


def test_policy_default_deny_dangerous_tool_names():
    for tool in ["deploy", "shell", "exec", "rm", "sudo", "network_write"]:
        step = AgentStep(
            step_id="s",
            kind=StepKind.SUMMARIZE,
            allowed_tools=[tool],
        )
        result = check_step_policy(step)
        assert result is not None, f"{tool} should be blocked"
        assert result.blocked is True


def test_policy_blocked_reason_does_not_leak_secrets():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        allowed_tools=[],
        goal="use api_key=sk-secret",
    )

    result = check_step_policy(step)

    assert result is not None
    assert "sk-secret" not in result.blocked_reason
    assert "api_key" not in result.blocked_reason
