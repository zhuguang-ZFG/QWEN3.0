"""Tests for Task #18: run_path intent support and protocol dispatch frame.

Covers:
- Intent parsing for run_path commands
- run_path_dispatch_frame construction
- params.path data format validation
- Protocol conversion end-to-end
"""

from device_gateway.intent import parse_command, resolve_voice_task
from device_gateway.protocol import run_path_dispatch_frame
from device_gateway.path_validator import validate_run_path_params, validate_capability_params


# ── Intent parsing ──────────────────────────────────────────────────

def test_parse_run_path_english():
    result = parse_command("run_path")
    assert result["capability"] == "run_path"
    assert result["confidence"] >= 0.9


def test_parse_run_path_with_space():
    result = parse_command("run path")
    assert result["capability"] == "run_path"
    assert result["confidence"] >= 0.9


def test_resolve_voice_task_run_path():
    result = resolve_voice_task("run path")
    assert result["capability"] == "run_path"
    assert result["source"] == "voice"


# ── Dispatch frame ──────────────────────────────────────────────────

def test_run_path_dispatch_frame_minimal():
    path = [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 10.0, "y": 20.0, "z": 1.0}]
    frame = run_path_dispatch_frame("d-1", "t-1", path)
    assert frame["type"] == "task_dispatch"
    assert frame["device_id"] == "d-1"
    assert frame["task_id"] == "t-1"
    assert frame["capability"] == "run_path"
    assert frame["params"]["path"] == path
    assert frame["params"]["feed"] == 500.0


def test_run_path_dispatch_frame_custom_feed():
    path = [{"x": 1.0, "y": 2.0}]
    frame = run_path_dispatch_frame("d-1", "t-1", path, feed=300.0)
    assert frame["params"]["feed"] == 300.0


def test_run_path_dispatch_frame_with_request_id():
    frame = run_path_dispatch_frame(
        "d-1", "t-1", [{"x": 0.0, "y": 0.0}], request_id="req-123"
    )
    assert frame["request_id"] == "req-123"


def test_run_path_dispatch_frame_with_extra_params():
    path = [{"x": 0.0, "y": 0.0}]
    extra = {"source_capability": "write_text", "text": "hello", "preview_svg": "<svg/>"}
    frame = run_path_dispatch_frame("d-1", "t-1", path, extra_params=extra)
    assert frame["params"]["source_capability"] == "write_text"
    assert frame["params"]["text"] == "hello"
    assert frame["params"]["preview_svg"] == "<svg/>"


def test_run_path_dispatch_frame_ignores_unknown_extra_keys():
    path = [{"x": 0.0, "y": 0.0}]
    frame = run_path_dispatch_frame(
        "d-1", "t-1", path, extra_params={"unknown_field": "ignored", "text": "keep"}
    )
    assert "unknown_field" not in frame["params"]
    assert frame["params"]["text"] == "keep"


# ── Path data format ────────────────────────────────────────────────

def test_validate_run_path_valid():
    path = [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 100.0, "y": 200.0, "z": 10.0}]
    params = {"path": path, "feed": 500.0}
    sanitized, error = validate_run_path_params(params)
    assert error is None
    assert sanitized["path"] == path
    assert sanitized["feed"] == 500.0


def test_validate_run_path_missing_path():
    sanitized, error = validate_run_path_params({"feed": 500.0})
    assert error is not None
    assert sanitized == {}


def test_validate_run_path_empty_path():
    sanitized, error = validate_run_path_params({"path": [], "feed": 500.0})
    assert error is not None


def test_validate_run_path_bad_coord_type():
    sanitized, error = validate_run_path_params(
        {"path": [{"x": "not_a_number", "y": 0}], "feed": 500.0}
    )
    assert error is not None


def test_validate_run_path_coord_out_of_range():
    sanitized, error = validate_run_path_params(
        {"path": [{"x": 1000.0, "y": 0.0}], "feed": 500.0}
    )
    assert error is not None


def test_validate_run_path_feed_out_of_range():
    sanitized, error = validate_run_path_params(
        {"path": [{"x": 0.0, "y": 0.0}], "feed": 0.1}
    )
    assert error is not None


def test_validate_run_path_too_many_points():
    path = [{"x": float(i), "y": 0.0} for i in range(201)]
    sanitized, error = validate_run_path_params({"path": path, "feed": 500.0})
    assert error is not None


def test_validate_run_path_negative_coords():
    path = [{"x": -100.0, "y": -200.0, "z": -50.0}]
    sanitized, error = validate_run_path_params({"path": path, "feed": 500.0})
    assert error is None
    assert sanitized["path"] == path


def test_validate_capability_run_path_with_params():
    path = [{"x": 10.0, "y": 20.0}]
    sanitized, error = validate_capability_params("run_path", {"path": path, "feed": 300.0})
    assert error is None
    assert sanitized["path"] == path
    assert sanitized["feed"] == 300.0


# ── Protocol conversion: intent → dispatch frame ─────────────────────

def test_intent_to_dispatch_frame_roundtrip():
    """A run_path intent should produce valid dispatch frame params."""
    # Simulate a parsed command
    voice_result = resolve_voice_task("run_path")
    assert voice_result["capability"] == "run_path"

    # Build dispatch params (as project_to_motion_task would)
    path = [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 50.0, "y": 50.0, "z": 0.0}]
    frame = run_path_dispatch_frame(
        device_id="dev-1",
        task_id="task-1",
        path=path,
        feed=500.0,
        extra_params={"source_capability": voice_result["capability"]},
    )

    assert frame["type"] == "task_dispatch"
    assert frame["capability"] == "run_path"
    assert len(frame["params"]["path"]) == 2
    # Frame params must pass validation
    sanitized, error = validate_run_path_params(frame["params"])
    assert error is None, f"dispatch frame params failed validation: {error}"


def test_run_path_frame_serializable():
    """Dispatch frame must be JSON-serializable."""
    import json

    path = [{"x": 1.5, "y": 2.5, "z": 0.0}]
    frame = run_path_dispatch_frame("d-1", "t-1", path, feed=300.0, request_id="r-1",
                                     extra_params={"text": "test"})
    serialized = json.dumps(frame)
    deserialized = json.loads(serialized)
    assert deserialized["type"] == "task_dispatch"
    assert deserialized["params"]["path"] == [{"x": 1.5, "y": 2.5, "z": 0.0}]


def test_run_path_z_defaults_to_zero():
    """Points without z should be accepted for basic 2D paths."""
    path = [{"x": 10.0, "y": 20.0}]
    sanitized, error = validate_run_path_params({"path": path, "feed": 500.0})
    assert error is None
    assert sanitized["path"][0].get("z", 0) == 0
