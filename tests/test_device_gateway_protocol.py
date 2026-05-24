import pytest

from device_gateway.intent import resolve_voice_task
from device_gateway.protocol import PROTOCOL_VERSION, ProtocolError, error_frame, validate_uplink
from device_gateway.safety import SafetyError, validate_run_path_params
from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests


def setup_function():
    reset_tasks_for_tests()


def test_validate_hello_normalizes_supported_message():
    msg = validate_uplink(
        {
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "device_id": "dev-1",
            "fw_rev": "u8-0.1.0",
            "capabilities": ["run_path"],
        }
    )

    assert msg["type"] == "hello"
    assert msg["device_id"] == "dev-1"
    assert msg["capabilities"] == ["run_path"]


def test_validate_rejects_unknown_message_type_with_stable_error():
    with pytest.raises(ProtocolError) as exc_info:
        validate_uplink({"type": "unknown", "request_id": "req-1"})

    frame = error_frame(exc_info.value)
    assert frame == {
        "type": "error",
        "code": "E_UNSUPPORTED_TYPE",
        "message": "message type is not supported",
        "request_id": "req-1",
    }


def test_resolves_write_text_voice_task():
    task = resolve_voice_task("写你好")

    assert task == {
        "capability": "write_text",
        "params": {"text": "你好"},
        "source": "voice",
    }


def test_resolves_draw_generated_voice_task():
    task = resolve_voice_task("画一个星星")

    assert task == {
        "capability": "draw_generated",
        "params": {"prompt": "一个星星"},
        "source": "voice",
    }


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


def test_safety_rejects_out_of_workspace_path():
    with pytest.raises(SafetyError):
        validate_run_path_params({"feed": 900, "path": [{"x": 999, "y": 0, "z": 0}]})


def test_motion_event_accepts_esp32_session_id_and_cancelled_phase():
    event = validate_uplink(
        {
            "type": "motion_event",
            "session_id": "dev-1",
            "task_id": "task-1",
            "phase": "cancelled",
            "progress": {"percent": 10},
        }
    )

    assert event["device_id"] == "dev-1"
    assert event["session_id"] == "dev-1"
    assert event["phase"] == "cancelled"
