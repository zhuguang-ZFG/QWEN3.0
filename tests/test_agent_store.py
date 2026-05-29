"""Tests for M18 agent runtime persistence, resume, query, and cleanup."""

import json
import os
import time

from agent_runtime import (
    AgentRunStore,
    ApprovalGate,
    InMemoryAgentRunStore,
    JsonlAgentRunStore,
    ResumeState,
)
from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentStep,
    AgentTask,
    StepKind,
    StepResult,
)
from agent_runtime.executor import AgentRuntime
from agent_runtime.resume import build_resume_state, format_resume_summary, resume_task
from agent_runtime.store import (
    compact_jsonl,
    count_by_status,
    delete_older_than,
    find_blocked,
    find_failed,
    list_recent,
    reset_store_for_tests,
)


def test_init_exports_store_and_resume_types():
    assert AgentRunStore is not None
    assert InMemoryAgentRunStore is not None
    assert JsonlAgentRunStore is not None
    assert ResumeState is not None


def test_in_memory_store_save_and_get():
    store = InMemoryAgentRunStore()
    task = AgentTask(task_id="t1", goal="test")

    assert store.save_task(task) is True
    assert store.get_task("t1") is not None
    assert store.get_task("t1").goal == "test"


def test_in_memory_store_save_result():
    store = InMemoryAgentRunStore()
    result = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED)

    assert store.save_result(result) is True
    assert store.get_result("t1").status == AgentRunStatus.COMPLETED


def test_in_memory_store_sanitizes_saved_records():
    store = InMemoryAgentRunStore()
    task = AgentTask(task_id="t1", goal="use api_key=sk-secret")
    result = AgentRunResult(
        task_id="t1",
        status=AgentRunStatus.COMPLETED,
        steps=[StepResult(step_id="s1", ok=True, output="token=secret")],
    )

    store.save_task(task)
    store.save_result(result)

    assert store.get_task("t1").goal == "[REDACTED]"
    assert store.get_result("t1").steps[0].output == "[REDACTED]"


def test_in_memory_store_list_tasks():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(task_id="a", goal="first"))
    store.save_task(AgentTask(task_id="b", goal="second"))

    tasks = store.list_tasks(limit=10)

    assert len(tasks) == 2


def test_in_memory_store_list_by_status():
    store = InMemoryAgentRunStore()
    task = AgentTask(task_id="t1", goal="test", status=AgentRunStatus.FAILED)
    store.save_task(task)

    assert len(store.list_tasks(status="failed")) == 1
    assert len(store.list_tasks(status="completed")) == 0


def test_in_memory_store_delete():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(task_id="t1", goal="test"))

    assert store.delete_task("t1") is True
    assert store.get_task("t1") is None
    assert store.delete_task("nonexistent") is False


def test_jsonl_store_save_and_get_task(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    task = AgentTask(task_id="t1", goal="test persistence")

    assert store.save_task(task) is True
    loaded = store.get_task("t1")

    assert loaded is not None
    assert loaded.task_id == "t1"


def test_jsonl_store_save_and_get_result(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    result = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED)

    store.save_result(result)
    loaded = store.get_result("t1")

    assert loaded is not None
    assert loaded.status == AgentRunStatus.COMPLETED


def test_jsonl_store_skips_bad_lines(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("not json\n")
        handle.write('{"_type":"task","task_id":"good","goal":"ok","status":"pending"}\n')
    store = JsonlAgentRunStore(path=path)

    tasks = store.list_tasks()

    assert len(tasks) == 1
    assert tasks[0].task_id == "good"


def test_jsonl_store_delete(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="t1", goal="test"))

    assert store.delete_task("t1") is True
    assert store.get_task("t1") is None


def test_jsonl_store_returns_latest_task_and_result(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="t1", goal="old", status=AgentRunStatus.RUNNING))
    store.save_task(AgentTask(task_id="t1", goal="new", status=AgentRunStatus.COMPLETED))
    store.save_result(AgentRunResult(task_id="t1", status=AgentRunStatus.FAILED))
    store.save_result(AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED))

    assert store.get_task("t1").goal == "new"
    assert store.get_task("t1").status == AgentRunStatus.COMPLETED
    assert store.get_result("t1").status == AgentRunStatus.COMPLETED


def test_jsonl_store_list_tasks_dedupes_latest_status(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="t1", goal="old", status=AgentRunStatus.RUNNING))
    store.save_task(AgentTask(task_id="t1", goal="new", status=AgentRunStatus.COMPLETED))

    assert len(store.list_tasks(limit=10)) == 1
    assert len(store.list_tasks(status="running", limit=10)) == 0
    assert len(store.list_tasks(status="completed", limit=10)) == 1


def test_jsonl_store_redacts_file_contents(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="t1", goal="api_key=sk-secret"))
    store.save_result(
        AgentRunResult(
            task_id="t1",
            status=AgentRunStatus.COMPLETED,
            steps=[StepResult(step_id="s1", ok=True, output="Bearer secret")],
        )
    )

    raw = open(path, encoding="utf-8").read()

    assert "sk-secret" not in raw
    assert "api_key" not in raw
    assert "Bearer secret" not in raw
    assert "[REDACTED]" in raw


def test_build_resume_state_completed_is_not_resumable():
    task = AgentTask(task_id="t1", goal="test")
    result = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED, steps=[])

    state = build_resume_state(task, result)

    assert state.can_resume is False
    assert state.next_action == "done"


def test_build_resume_state_failed():
    task = AgentTask(task_id="t1", goal="test")
    result = AgentRunResult(
        task_id="t1",
        status=AgentRunStatus.FAILED,
        steps=[StepResult(step_id="s1", ok=False, error="hook error")],
    )

    state = build_resume_state(task, result)

    assert state.can_resume is True
    assert state.failed_step == "s1"
    assert state.next_action == "fix_error_and_retry"


def test_build_resume_state_blocked_completed_result_can_resume():
    task = AgentTask(task_id="t1", goal="deploy")
    result = AgentRunResult(
        task_id="t1",
        status=AgentRunStatus.COMPLETED,
        steps=[StepResult(step_id="s1", ok=False, blocked=True)],
    )

    state = build_resume_state(task, result)

    assert state.can_resume is True
    assert state.blocked_steps == ["s1"]
    assert state.next_action == "approve_blocked_steps"


def test_resume_state_to_dict_redacts_secrets():
    state = ResumeState(
        task_id="token=secret",
        status=AgentRunStatus.FAILED,
        completed_steps=["ok"],
        blocked_steps=["api_key=sk-secret"],
        failed_step="password=secret",
        next_action="fix_error_and_retry",
        can_resume=True,
        resume_note="token=secret",
    )

    data = state.to_dict()

    assert data["task_id"] == "[REDACTED]"
    assert data["blocked_steps"] == ["[REDACTED]"]
    assert data["failed_step"] == "[REDACTED]"
    assert data["resume_note"] == "[REDACTED]"


def test_resume_task_via_store():
    store = InMemoryAgentRunStore()
    task = AgentTask(task_id="t1", goal="test")
    result = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED, steps=[])
    store.save_task(task)
    store.save_result(result)

    state = resume_task("t1", store)

    assert state is not None
    assert state.can_resume is False


def test_resume_task_missing():
    store = InMemoryAgentRunStore()

    assert resume_task("nonexistent", store) is None


def test_format_resume_summary_redacts_secrets():
    state = ResumeState(
        task_id="token=secret",
        status=AgentRunStatus.FAILED,
        next_action="fix_error_and_retry",
        can_resume=True,
        resume_note="api_key=sk-secret",
    )

    text = format_resume_summary(state)

    assert "[REDACTED]" in text
    assert "token=secret" not in text
    assert "api_key" not in text


def test_runtime_with_store_saves_task_and_result():
    store = InMemoryAgentRunStore()
    runtime = AgentRuntime(store=store)
    task = AgentTask(task_id="store-test", goal="review the code")

    runtime.run(task)

    assert store.get_task("store-test") is not None
    assert store.get_task("store-test").status == AgentRunStatus.COMPLETED
    assert store.get_result("store-test") is not None
    assert store.get_result("store-test").status == AgentRunStatus.COMPLETED


def test_runtime_without_store_does_not_crash():
    runtime = AgentRuntime()
    task = AgentTask(task_id="t1", goal="test")

    result = runtime.run(task)

    assert result.ok is True


def test_runtime_stores_blocked_result():
    store = InMemoryAgentRunStore()
    runtime = AgentRuntime(store=store)
    task = AgentTask(
        task_id="blocked-test",
        goal="deploy to production",
        allowed_tools=["shell"],
    )

    runtime.run(task)
    result = store.get_result("blocked-test")

    assert result is not None
    assert any(step.blocked for step in result.steps)


def test_runtime_with_approval_gate_blocks_shell():
    gate = ApprovalGate(dry_run=True)
    rt = AgentRuntime(approval_gate=gate)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="deploy")
    result = rt.run_step(step)
    assert result.blocked is True
    assert "shell" in result.blocked_reason.lower()


def test_runtime_with_approval_gate_allows_safe():
    gate = ApprovalGate(dry_run=True)
    rt = AgentRuntime(approval_gate=gate)
    step = AgentStep(step_id="s1", kind=StepKind.SUMMARIZE, goal="summarize")
    result = rt.run_step(step)
    assert result.ok is True
    assert not result.blocked


def test_runtime_without_approval_gate_unchanged():
    rt = AgentRuntime()
    step = AgentStep(step_id="s1", kind=StepKind.SUMMARIZE, goal="test")
    result = rt.run_step(step)
    assert result.ok is True


def test_runtime_approval_checked_before_execution():
    gate = ApprovalGate(dry_run=False)
    rt = AgentRuntime(approval_gate=gate)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")
    result = rt.run_step(step)
    assert result.blocked is True
    assert "approval required" in result.blocked_reason.lower()
    assert len(gate.get_pending()) == 1


def test_runtime_approved_allows_exact_task_step_surface():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, goal="run tests")
    gate.check_step(step, task_id="task-1")
    gate.approve(gate.get_pending()[0].approval_id)
    rt = AgentRuntime(approval_gate=gate)
    result = rt.run_step(step, task_id="task-1")
    assert result.ok is True
    assert not result.blocked


def test_runtime_approval_does_not_cross_task_ids():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, goal="run tests")
    gate.check_step(step, task_id="approved-task")
    gate.approve(gate.get_pending()[0].approval_id)
    runtime = AgentRuntime(approval_gate=gate)

    result = runtime.run_step(step, task_id="other-task")

    assert result.blocked is True
    assert "approval required" in result.blocked_reason.lower()


def test_runtime_run_passes_task_id_to_approval_gate():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, goal="run tests")
    gate.check_step(step, task_id="task-1")
    gate.approve(gate.get_pending()[0].approval_id)
    runtime = AgentRuntime(approval_gate=gate)
    task = AgentTask(task_id="task-1", goal="run tests", steps=[step])

    result = runtime.run(task)

    assert result.ok is True
    assert result.steps[0].blocked is False


def test_list_recent():
    store = InMemoryAgentRunStore()
    for index in range(5):
        store.save_task(AgentTask(task_id=f"t{index}", goal=f"task {index}"))

    assert len(list_recent(store, limit=3)) == 3


def test_count_by_status():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(task_id="ok", goal="x", status=AgentRunStatus.COMPLETED))
    store.save_task(AgentTask(task_id="fail", goal="x", status=AgentRunStatus.FAILED))
    store.save_task(AgentTask(task_id="pend", goal="x", status=AgentRunStatus.PENDING))

    counts = count_by_status(store)

    assert counts.get("completed", 0) == 1
    assert counts.get("failed", 0) == 1
    assert counts.get("pending", 0) == 1


def test_find_blocked_uses_results_not_planned_shell_steps():
    store = InMemoryAgentRunStore()
    planned_shell = AgentTask(
        task_id="planned",
        goal="deploy",
        steps=[AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND)],
    )
    blocked_task = AgentTask(task_id="blocked", goal="deploy")
    blocked_result = AgentRunResult(
        task_id="blocked",
        status=AgentRunStatus.COMPLETED,
        steps=[StepResult(step_id="s1", ok=False, blocked=True)],
    )
    store.save_task(planned_shell)
    store.save_task(blocked_task)
    store.save_result(blocked_result)

    blocked = find_blocked(store)

    assert [task.task_id for task in blocked] == ["blocked"]


def test_find_failed():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(task_id="ok", goal="x", status=AgentRunStatus.COMPLETED))
    store.save_task(AgentTask(task_id="bad", goal="x", status=AgentRunStatus.FAILED))

    failed = find_failed(store)

    assert len(failed) == 1
    assert failed[0].task_id == "bad"


def test_delete_older_than():
    store = InMemoryAgentRunStore()
    old = AgentTask(task_id="old", goal="old", created_at=100)
    new = AgentTask(task_id="new", goal="new", created_at=time.time())
    store.save_task(old)
    store.save_task(new)

    deleted = delete_older_than(store, cutoff_ts=time.time() - 1000)

    assert deleted == 1
    assert store.get_task("new") is not None


def test_compact_jsonl_keeps_latest_records(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="compact-test", goal="old"))
    store.save_task(AgentTask(task_id="compact-test", goal="new"))
    store.save_result(AgentRunResult(task_id="compact-test", status=AgentRunStatus.FAILED))
    store.save_result(AgentRunResult(task_id="compact-test", status=AgentRunStatus.COMPLETED))

    kept = compact_jsonl(path)
    loaded = JsonlAgentRunStore(path=path).get_task("compact-test")
    result = JsonlAgentRunStore(path=path).get_result("compact-test")

    assert kept == 2
    assert loaded is not None
    assert loaded.goal == "new"
    assert result.status == AgentRunStatus.COMPLETED


def test_compact_jsonl_handles_bad_lines(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("not json\n")
        handle.write(json.dumps({
            "_type": "task",
            "task_id": "good",
            "goal": "ok",
            "status": "pending",
        }))
        handle.write("\n")

    kept = compact_jsonl(path)

    assert kept == 1


def test_reset_store_for_tests(tmp_path):
    path = str(tmp_path / "runs.jsonl")
    store = JsonlAgentRunStore(path=path)
    store.save_task(AgentTask(task_id="t1", goal="test"))

    reset_store_for_tests(path)

    assert not os.path.exists(path)
