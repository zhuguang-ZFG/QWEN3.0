from device_artifacts.store import artifact_store
from device_gateway.model_routing import resolve_device_route_policy
from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests


def setup_function():
    reset_tasks_for_tests()


def test_control_command_uses_no_model_route():
    task = create_task_from_transcript("dev-1", "home")

    assert task["route_policy"]["route_role"] == "device_control"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["primary_strategy"] == "deterministic"


def test_write_text_uses_device_write_route():
    task = create_task_from_transcript("dev-1", "write LiMa")

    assert task["route_policy"]["route_role"] == "device_write"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["artifact_required"] == "preview_svg"


def test_generated_drawing_uses_device_draw_route():
    task = create_task_from_transcript("dev-1", "draw cat")

    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["route_policy"]["model_required"] is True
    assert task["route_policy"]["artifact_required"] == "vector_path"


def test_svg_like_generated_drawing_uses_vector_route_without_model():
    policy = resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}}
    )

    assert policy["route_role"] == "device_vector"
    assert policy["model_required"] is False


def test_route_evidence_artifact_recorded_for_created_task():
    task = create_task_from_transcript("dev-1", "draw cat")

    records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
    assert len(records) == 1
    evidence = records[0].content
    assert evidence["route_role"] == "device_draw"
    assert evidence["primary_strategy"] == "image_then_vector"
    assert evidence["model_required"] is True
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
