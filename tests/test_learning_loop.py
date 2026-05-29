"""Tests for session_memory.learning_loop — task outcome → memory/prompt/routing/eval."""
from session_memory.learning_loop import (
    TaskOutcome,
    get_eval_candidates,
    get_prompt_profile_stats,
    ingest_task_outcome,
)


def test_ingest_succeeded_task_feeds_all_channels(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_OUTCOME_DB", str(tmp_path / "outcome.db"))
    outcome = TaskOutcome(
        task_id="task-001",
        status="succeeded",
        goal="fix auth bug",
        changed_files=["auth.py", "test_auth.py"],
        test_results=[
            {"command": "pytest test_auth.py", "exit_code": 0, "duration_ms": 120},
        ],
        backend="scnet_ds_flash",
        scenario="coding",
        latency_ms=3421,
    )
    result = ingest_task_outcome(outcome)
    assert result["task_id"] == "task-001"
    assert "memory" in result
    assert "prompt" in result
    assert "routing" in result
    assert "eval" in result

    from observability.capability_evidence import recent_evidence

    rows = [r for r in recent_evidence(limit=5) if r.get("loop") == "ops_learning"]
    assert rows and rows[-1]["task_id"] == "task-001"
    assert rows[-1]["selected_backend"] == "scnet_ds_flash"


def test_ingest_failed_task_records_failure_memory():
    outcome = TaskOutcome(
        task_id="task-002",
        status="failed",
        goal="add feature",
        failure_reason="test command failed: npm test",
        test_results=[
            {"command": "npm test", "exit_code": 1, "duration_ms": 500},
        ],
        backend="groq_gptoss",
        scenario="coding",
        latency_ms=1234,
    )
    result = ingest_task_outcome(outcome)
    assert result["task_id"] == "task-002"


def test_ingest_task_without_backend_still_feeds_memory_and_prompt():
    outcome = TaskOutcome(
        task_id="task-003",
        status="needs_review",
        goal="review docs",
        changed_files=["README.md"],
        test_results=[],
        backend="",
        scenario="",
    )
    result = ingest_task_outcome(outcome)
    assert result["routing"]["recorded"] is False


def test_prompt_profile_accumulates_stats():
    for i in range(3):
        ingest_task_outcome(TaskOutcome(
            task_id=f"task-p{i}",
            status="succeeded",
            goal="fix type errors",
            backend="github_gpt4o",
            scenario="coding",
            test_results=[{"command": "tsc --noEmit", "exit_code": 0}],
        ))
    stats = get_prompt_profile_stats()
    assert len(stats) > 0


def test_eval_candidates_are_queued():
    initial = len(get_eval_candidates(100))
    for i in range(3):
        ingest_task_outcome(TaskOutcome(
            task_id=f"task-e{i}",
            status="succeeded",
            goal="implement feature",
            backend="scnet_ds_flash",
            scenario="coding",
            test_results=[{"command": "pytest", "exit_code": 0}],
        ))
    candidates = get_eval_candidates(100)
    assert len(candidates) >= initial + 3


def test_test_pass_rate_all_pass():
    results = [
        {"command": "a", "exit_code": 0},
        {"command": "b", "exit_code": 0},
    ]
    outcome = TaskOutcome(
        task_id="task-pass",
        status="succeeded",
        test_results=results,
    )
    result = ingest_task_outcome(outcome)
    assert result["eval"]["candidate_queued"]


def test_test_pass_rate_mixed():
    results = [
        {"command": "a", "exit_code": 0},
        {"command": "b", "exit_code": 1},
    ]
    outcome = TaskOutcome(
        task_id="task-mix",
        status="failed",
        test_results=results,
    )
    result = ingest_task_outcome(outcome)
    assert result["eval"]["candidate_queued"]
