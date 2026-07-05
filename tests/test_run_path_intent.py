"""Tests for Task #18: run_path intent support.

Covers:
- Intent parsing for run_path commands
- params.path data format validation
"""

from device_gateway.intent import parse_command, resolve_voice_task
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
    sanitized, error = validate_run_path_params({"path": [{"x": "not_a_number", "y": 0}], "feed": 500.0})
    assert error is not None


def test_validate_run_path_coord_out_of_range():
    sanitized, error = validate_run_path_params({"path": [{"x": 1000.0, "y": 0.0}], "feed": 500.0})
    assert error is not None


def test_validate_run_path_feed_out_of_range():
    sanitized, error = validate_run_path_params({"path": [{"x": 0.0, "y": 0.0}], "feed": 0.1})
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


def test_validate_run_path_z_defaults_to_zero():
    """Points without z should be accepted for basic 2D paths."""
    path = [{"x": 10.0, "y": 20.0}]
    sanitized, error = validate_run_path_params({"path": path, "feed": 500.0})
    assert error is None
    assert sanitized["path"][0].get("z", 0) == 0
