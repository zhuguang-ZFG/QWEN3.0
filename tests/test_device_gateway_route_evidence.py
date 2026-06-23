"""Route evidence artifact tests."""

from unittest.mock import AsyncMock, patch

import pytest

from device_artifacts.store import artifact_store
from device_gateway.tasks import (
    create_task_from_transcript,
    execute_recovery,
    mark_task_dispatched,
    project_to_motion_task,
    record_motion_event,
    reset_tasks_for_tests,
)
import device_gateway.task_creation as task_creation


def setup_function():
    reset_tasks_for_tests()


@pytest.fixture(autouse=True)
def _mock_device_draw(monkeypatch):
    monkeypatch.setattr(
        "device_gateway.task_draw_params.handle_device_draw",
        AsyncMock(
            return_value={
                "status": "success",
                "image_url": "",
                "svg_path": "M 10 10 L 50 50 L 90 10 Z",
                "width": 180,
                "height": 180,
                "model": "test-draw",
                "error": None,
            }
        ),
    )


def test_route_evidence_artifact_recorded_for_created_task():
    mock_draw = AsyncMock(
        return_value={
            "status": "success",
            "image_url": "http://example.com/cat.jpg",
            "svg_path": "M 10 10 L 50 50 L 90 10 Z",
            "width": 180,
            "height": 180,
            "model": "wanx2.1-t2i-turbo",
            "error": None,
        }
    )
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = create_task_from_transcript("dev-1", "draw cat")

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    assert len(records) == 1
    evidence = records[0].content
    assert evidence["route_role"] == "device_draw"
    assert evidence["primary_strategy"] == "image_then_vector"
    assert evidence["model_required"] is True
    assert evidence["backend"] == "dashscope_wanx"
    assert evidence["scenario"] == "task_created"
    assert evidence["capability"] == "run_path"
    assert "policy_decision" in evidence
    assert "sim_risk_score" in evidence
    assert "workflow_state" in evidence


def test_route_evidence_artifact_recorded_for_control_task():
    task = create_task_from_transcript("dev-1", "home")

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    assert len(records) == 1
    evidence = records[0].content
    assert evidence["route_role"] == "device_control"
    assert evidence["primary_strategy"] == "deterministic"
    assert evidence["model_required"] is False


def test_route_evidence_artifact_recorded_for_write_task():
    task = create_task_from_transcript("dev-1", "write LiMa")

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    assert len(records) == 1
    evidence = records[0].content
    assert evidence["route_role"] == "device_write"
    assert evidence["artifact_required"] == "preview_svg"


def test_route_evidence_includes_error_on_validation_failure():
    """When route_policy validation fails, the task should have an error and evidence should record it."""
    original = task_creation.resolve_device_route_policy

    def bad_policy(voice_task, device_id="", **kwargs):
        return {
            "route_role": "INVALID",
            "model_required": False,
            "primary_strategy": "bad",
            "artifact_required": "nope",
        }

    task_creation.resolve_device_route_policy = bad_policy
    try:
        task = project_to_motion_task("dev-1", {"capability": "home", "params": {}})
        assert task.get("error") is not None
        assert task["error"]["code"] != ""
        # Evidence should be recorded even for failed tasks
        records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
        assert len(records) == 1
        evidence = records[0].content
        assert evidence["route_role"] == "INVALID"
        assert evidence["scenario"] == "route_policy_invalid"
        assert evidence.get("error_code") != ""
    finally:
        task_creation.resolve_device_route_policy = original


def test_route_evidence_scenario_on_param_validation_failure():
    original = task_creation.validate_capability_params
    task_creation.validate_capability_params = lambda cap, params: ({}, "E_BAD_PARAMS")
    try:
        task = create_task_from_transcript("dev-1", "write LiMa")
        records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
        assert len(records) == 1
        assert records[0].content["scenario"] == "validation_failed"
        assert records[0].content["backend"] == "deterministic"
    finally:
        task_creation.validate_capability_params = original


def test_device_consumed_route_evidence_on_terminal_motion_event():
    from device_gateway.tasks import mark_task_dispatched, record_motion_event

    task = create_task_from_transcript("dev-1", "draw cat")
    mark_task_dispatched(task["task_id"])
    record_motion_event(
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": task["task_id"],
            "phase": "done",
            "route_policy_evidence": {
                "consumed": True,
                "route_role": "device_draw",
                "model_required": True,
                "primary_strategy": "image_then_vector",
                "artifact_required": "vector_path",
                "backend": "dashscope_wanx",
            },
        }
    )

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    consumed = [record for record in records if record.content.get("scenario") == "device_consumed"]
    assert len(consumed) == 1
    assert consumed[0].content["backend"] == "dashscope_wanx"
    assert consumed[0].content["phase"] == "done"


def test_recovery_route_evidence_recorded_on_failed_motion_event():
    from device_gateway.tasks import execute_recovery, mark_task_dispatched, record_motion_event

    task = create_task_from_transcript("dev-1", "write LiMa")
    mark_task_dispatched(task["task_id"])
    event = {
        "type": "motion_event",
        "device_id": "dev-1",
        "task_id": task["task_id"],
        "phase": "failed",
        "error": {"code": "E_MISSING_PATH", "reason": "path missing"},
    }
    record_motion_event(event)
    execute_recovery(task["task_id"], "dev-1", event)

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    recovery = [record for record in records if record.content.get("scenario") == "recovery"]
    assert len(recovery) == 1
    assert recovery[0].content["recovery_action"] == "retry"
    assert recovery[0].content["route_role"] == "device_write"
    assert recovery[0].content["backend"] == "deterministic"
