from device_artifacts.store import artifact_store
from device_gateway.model_routing import (
    DEVICE_ROLE_PREFERENCES,
    get_preferred_backend,
    get_route_role_alternatives,
    resolve_device_route_policy,
)
from device_gateway.path_validator import validate_route_policy
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
    policy = resolve_device_route_policy({"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}})

    assert policy["route_role"] == "device_vector"
    assert policy["model_required"] is False


def test_route_policy_matrix_for_hot_device_families():
    cases = [
        (
            {"capability": "home", "params": {}},
            {
                "route_role": "device_control",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "none",
                "backend": "deterministic",
            },
        ),
        (
            {"capability": "write_text", "params": {"text": "你好"}},
            {
                "route_role": "device_write",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "preview_svg",
                "backend": "deterministic",
            },
        ),
        (
            {"capability": "draw_generated", "params": {"prompt": "画一只猫"}},
            {
                "route_role": "device_draw",
                "model_required": True,
                "primary_strategy": "image_then_vector",
                "artifact_required": "vector_path",
                "backend": "dashscope_wanx",
            },
        ),
        (
            {"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}},
            {
                "route_role": "device_vector",
                "model_required": False,
                "primary_strategy": "svg_vector",
                "artifact_required": "preview_svg",
                "backend": "opencv_contour",
            },
        ),
    ]

    for voice_task, expected in cases:
        assert resolve_device_route_policy(voice_task) == expected


def test_route_evidence_artifact_recorded_for_created_task():
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


# ── Route policy validation tests ────────────────────────────────────────────


def test_validate_route_policy_accepts_valid_control():
    policy = {
        "route_role": "device_control",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    validated, error = validate_route_policy(policy, "home")
    assert error is None
    assert validated["route_role"] == "device_control"


def test_validate_route_policy_rejects_unknown_role():
    policy = {
        "route_role": "unknown_role",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_rejects_control_with_model():
    policy = {
        "route_role": "device_control",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy, "home")
    assert error is not None


def test_validate_route_policy_rejects_draw_without_model():
    policy = {
        "route_role": "device_draw",
        "model_required": False,
        "primary_strategy": "image_then_vector",
        "artifact_required": "vector_path",
    }
    _, error = validate_route_policy(policy, "draw_generated")
    assert error is not None


def test_validate_route_policy_rejects_draw_wrong_strategy():
    policy = {
        "route_role": "device_draw",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "vector_path",
    }
    _, error = validate_route_policy(policy, "draw_generated")
    assert error is not None


def test_validate_route_policy_rejects_unknown_not_planner():
    policy = {
        "route_role": "device_unknown",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_rejects_invalid_artifact():
    policy = {
        "route_role": "device_write",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "invalid",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_accepts_valid_draw():
    policy = {
        "route_role": "device_draw",
        "model_required": True,
        "primary_strategy": "image_then_vector",
        "artifact_required": "vector_path",
    }
    validated, error = validate_route_policy(policy, "draw_generated")
    assert error is None
    assert validated["route_role"] == "device_draw"


def test_validate_route_policy_accepts_valid_vector():
    policy = {
        "route_role": "device_vector",
        "model_required": False,
        "primary_strategy": "svg_vector",
        "artifact_required": "preview_svg",
    }
    validated, error = validate_route_policy(policy, "draw_generated")
    assert error is None
    assert validated["route_role"] == "device_vector"


def test_validate_route_policy_accepts_valid_write():
    policy = {
        "route_role": "device_write",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "preview_svg",
    }
    validated, error = validate_route_policy(policy, "write_text")
    assert error is None
    assert validated["route_role"] == "device_write"


def test_validate_route_policy_rejects_non_dict():
    _, error = validate_route_policy("not a dict")
    assert error is not None


def test_route_evidence_includes_error_on_validation_failure():
    """When route_policy validation fails, the task should have an error and evidence should record it."""
    from device_gateway.tasks import project_to_motion_task

    # Manually create a voice_task that would produce an invalid route_policy
    # by patching resolve_device_route_policy to return an invalid policy
    import device_gateway.task_deps as task_deps

    original = task_deps.resolve_device_route_policy

    def bad_policy(voice_task, device_id="", **kwargs):
        return {
            "route_role": "INVALID",
            "model_required": False,
            "primary_strategy": "bad",
            "artifact_required": "nope",
        }

    task_deps.resolve_device_route_policy = bad_policy
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
        task_deps.resolve_device_route_policy = original


def test_route_evidence_scenario_on_param_validation_failure():
    import device_gateway.task_deps as task_deps

    original = task_deps.validate_capability_params
    task_deps.validate_capability_params = lambda cap, params: ({}, "E_BAD_PARAMS")
    try:
        task = create_task_from_transcript("dev-1", "write LiMa")
        records = artifact_store.artifacts_for_task(task["task_id"], "route_evidence")
        assert len(records) == 1
        assert records[0].content["scenario"] == "validation_failed"
        assert records[0].content["backend"] == "deterministic"
    finally:
        task_deps.validate_capability_params = original


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


# ── Device role routing preference tests ────────────────────────────────────


def test_get_preferred_backend_for_control():
    result = get_preferred_backend("device_control")
    assert result is not None
    assert result["backend"] == "deterministic"


def test_get_preferred_backend_for_draw():
    result = get_preferred_backend("device_draw")
    assert result is not None
    assert result["backend"] == "dashscope_wanx"


def test_get_preferred_backend_for_write():
    result = get_preferred_backend("device_write")
    assert result is not None
    assert result["backend"] == "deterministic"


def test_get_preferred_backend_for_vector():
    result = get_preferred_backend("device_vector")
    assert result is not None
    assert result["backend"] == "opencv_contour"


def test_get_preferred_backend_for_unknown_role():
    result = get_preferred_backend("nonexistent_role")
    assert result is None


def test_get_route_role_alternatives_for_draw():
    alternatives = get_route_role_alternatives("device_draw")
    assert len(alternatives) == 2
    assert alternatives[0]["backend"] == "dashscope_wanx"
    assert alternatives[1]["backend"] == "dashscope_flux"


def test_get_route_role_alternatives_for_control():
    alternatives = get_route_role_alternatives("device_control")
    assert len(alternatives) == 1
    assert alternatives[0]["backend"] == "deterministic"


def test_get_route_role_alternatives_for_unknown():
    alternatives = get_route_role_alternatives("nonexistent_role")
    assert len(alternatives) == 0


def test_device_role_preferences_covers_all_roles():
    """All valid route roles should have preferences defined."""
    valid_roles = {"device_control", "device_write", "device_draw", "device_vector", "device_unknown"}
    for role in valid_roles:
        assert role in DEVICE_ROLE_PREFERENCES, f"Missing preferences for {role}"
        assert len(DEVICE_ROLE_PREFERENCES[role]) > 0, f"Empty preferences for {role}"
