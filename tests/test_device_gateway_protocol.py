import pytest

from device_gateway.intent import resolve_voice_task
from device_gateway.safety import SafetyError, validate_run_path_params
from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests


def setup_function():
    reset_tasks_for_tests()


def test_resolves_write_text_voice_task():
    task = resolve_voice_task("写你好")

    assert task["capability"] == "write_text"
    assert task["params"] == {"text": "你好"}
    assert task["source"] == "voice"
    assert "explanation" in task


def test_resolves_draw_generated_voice_task():
    task = resolve_voice_task("画一个星星")

    assert task["capability"] == "draw_generated"
    assert task["params"] == {"prompt": "一个星星"}
    assert task["source"] == "voice"
    assert "explanation" in task


def test_resolve_voice_task_unknown_is_rejected_without_motion():
    # GW-WH: unknown speech must not become pen motion (old write_text fallback).
    task = resolve_voice_task("xyzzy something weird")
    assert task["capability"] == "rejected"
    assert task["params"] == {}


def test_resolve_voice_task_empty_is_rejected():
    task = resolve_voice_task("")
    assert task["capability"] == "rejected"
    assert task["params"] == {}


def test_transcript_projects_to_bounded_run_path_motion_task():
    motion_task = create_task_from_transcript("dev-1", "画一个星星", request_id="req-1")

    assert motion_task["type"] == "motion_task"
    assert motion_task["device_id"] == "dev-1"
    assert motion_task["capability"] == "run_path"
    assert motion_task["request_id"] == "req-1"
    assert motion_task["params"]["source_capability"] == "draw_generated"
    assert motion_task["params"]["feed"] <= 1200
    assert 1 <= len(motion_task["params"]["path"]) <= 128
    assert all(0 <= point["x"] <= 100 and 0 <= point["y"] <= 100 for point in motion_task["params"]["path"])


def test_transcript_preserves_preview_svg_for_operator_replay():
    motion_task = create_task_from_transcript("dev-1", "write LiMa", request_id="req-preview")

    preview = motion_task["params"]["preview_svg"]
    assert motion_task["params"]["source_capability"] == "write_text"
    assert preview.startswith("<svg")
    assert preview.endswith("</svg>")
    assert "LiMa" in preview


def test_transcript_projects_control_command_to_control_motion_task():
    motion_task = create_task_from_transcript("dev-1", "home", request_id="req-home")

    assert motion_task["type"] == "motion_task"
    assert motion_task["device_id"] == "dev-1"
    assert motion_task["capability"] == "home"
    assert motion_task["request_id"] == "req-home"
    assert motion_task["params"] == {"source_capability": "home"}
    assert "error" not in motion_task


def test_safety_rejects_out_of_workspace_path():
    with pytest.raises(SafetyError):
        validate_run_path_params({"feed": 900, "path": [{"x": 999, "y": 0, "z": 0}]})
