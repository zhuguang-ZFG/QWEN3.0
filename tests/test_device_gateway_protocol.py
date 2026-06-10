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


def test_resolve_voice_task_unknown_falls_back_with_low_confidence():
    task = resolve_voice_task("xyzzy something weird")
    assert task["capability"] == "write_text"
    assert task["params"]["text"] == "xyzzy something weird"


def test_resolve_voice_task_empty_returns_hello():
    task = resolve_voice_task("")
    assert task["capability"] == "write_text"
    assert task["params"]["text"] == "hello"


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


def test_validate_voiceprint_sample_normalizes_and_validates():
    msg = validate_uplink(
        {
            "type": "voiceprint_sample",
            "device_id": "dev-1",
            "voiceprint_id": "vp-1",
            "sample_index": 5,
            "audio_data": "sample audio data",
            "format": "raw_pcm",
        }
    )

    assert msg["type"] == "voiceprint_sample"
    assert msg["device_id"] == "dev-1"
    assert msg["voiceprint_id"] == "vp-1"
    assert msg["sample_index"] == 5
    assert msg["audio_data"] == "sample audio data"
    assert msg["format"] == "raw_pcm"


def test_validate_voiceprint_sample_rejects_invalid_format():
    with pytest.raises(ProtocolError) as exc_info:
        validate_uplink(
            {
                "type": "voiceprint_sample",
                "device_id": "dev-1",
                "voiceprint_id": "vp-1",
                "sample_index": 0,
                "audio_data": "data",
                "format": "invalid_format",
            }
        )

    assert exc_info.value.code == "E_INVALID_MESSAGE"
    assert "format must be one of raw_pcm, wav, opus, g711, or pcm" in exc_info.value.message


def test_validate_voiceprint_sample_rejects_invalid_sample_index():
    with pytest.raises(ProtocolError) as exc_info:
        validate_uplink(
            {
                "type": "voiceprint_sample",
                "device_id": "dev-1",
                "voiceprint_id": "vp-1",
                "sample_index": -1,
                "audio_data": "data",
            }
        )

    assert exc_info.value.code == "E_INVALID_MESSAGE"
    assert "sample_index must be a non-negative integer" in exc_info.value.message


def test_build_voiceprint_sample_ack_contains_required_fields():
    from device_gateway.protocol import build_voiceprint_sample_ack

    ack = build_voiceprint_sample_ack(
        device_id="dev-1",
        voiceprint_id="vp-1",
        sample_index=3,
        request_id="req-1",
    )

    assert ack["type"] == "voiceprint_sample_ack"
    assert ack["device_id"] == "dev-1"
    assert ack["voiceprint_id"] == "vp-1"
    assert ack["sample_index"] == 3
    assert ack["request_id"] == "req-1"
    assert "server_time" in ack
