from agent_runtime.summary_constraints import (
    REQUIRED_SUMMARY_FIELDS,
    WorkerSummary,
    action_is_gated,
    validate_worker_summary,
)


def test_validate_worker_summary_accepts_required_fields():
    summary = validate_worker_summary({
        "changed_files": ["server.py"],
        "tests_run": ["pytest tests/test_server.py"],
        "remaining_risks": ["manual deploy not exercised"],
        "review_status": "needs_review",
    })

    assert isinstance(summary, WorkerSummary)
    assert summary.is_complete()
    assert summary.to_dict()["review_status"] == "needs_review"


def test_validate_worker_summary_rejects_missing_required_field():
    data = {field: [] for field in REQUIRED_SUMMARY_FIELDS}
    data.pop("tests_run")

    assert validate_worker_summary(data) is None


def test_validate_worker_summary_rejects_invalid_review_status():
    summary = validate_worker_summary({
        "changed_files": ["server.py"],
        "tests_run": ["pytest"],
        "remaining_risks": [],
        "review_status": "ship_it",
    })

    assert summary is None


def test_validate_worker_summary_rejects_scalar_list_fields():
    summary = validate_worker_summary({
        "changed_files": "server.py",
        "tests_run": ["pytest"],
        "remaining_risks": [],
        "review_status": "approved",
    })

    assert summary is None


def test_action_gate_marks_dangerous_outputs():
    assert action_is_gated("deploy")
    assert action_is_gated("push")
    assert action_is_gated("hardware_command")
    assert not action_is_gated("read_file")
