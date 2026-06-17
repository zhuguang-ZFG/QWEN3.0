"""Tests for device_gateway.path_validator."""

from device_gateway.path_validator import (
    validate_capability_params,
    validate_run_path_params,
    CAPABILITY_PATH_MAP,
    MAX_PATH_POINTS,
)


def test_validate_run_path_params_accepts_valid_path():
    params = {"path": [{"x": 10, "y": 20, "z": 0}], "feed": 500}
    sanitized, error = validate_run_path_params(params)
    assert error is None
    assert len(sanitized["path"]) == 1


def test_validate_run_path_params_rejects_empty_path():
    _, error = validate_run_path_params({"path": [], "feed": 500})
    assert error == "E_MISSING_PATH"


def test_validate_run_path_params_rejects_missing_path():
    _, error = validate_run_path_params({"feed": 500})
    assert error == "E_MISSING_PATH"


def test_validate_run_path_params_rejects_non_dict_params():
    _, error = validate_run_path_params("not a dict")
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_oversized_path():
    path = [{"x": 0, "y": 0, "z": 0}] * (MAX_PATH_POINTS + 1)
    _, error = validate_run_path_params({"path": path, "feed": 500})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_out_of_bounds_point():
    _, error = validate_run_path_params({"path": [{"x": 9999, "y": 0, "z": 0}], "feed": 500})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_invalid_feed():
    _, error = validate_run_path_params({"path": [{"x": 0, "y": 0, "z": 0}], "feed": 9999})
    assert error == "E_BAD_PARAMS"


def test_validate_capability_params_rejects_unknown_capability():
    _, error = validate_capability_params("laser_engrave", {"path": [{"x": 0, "y": 0}], "feed": 500})
    assert error == "E_UNSUPPORTED_CAPABILITY"


def test_validate_capability_params_accepts_write_text_with_text_field():
    params = {"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500, "text": "hello"}
    sanitized, error = validate_capability_params("write_text", params)
    assert error is None
    assert sanitized["text"] == "hello"


def test_validate_capability_params_rejects_write_text_without_text():
    params = {"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500}
    _, error = validate_capability_params("write_text", params)
    assert error == "E_BAD_PARAMS"


def test_validate_capability_params_preserves_preview_svg():
    preview = "<svg>" + ("x" * 300) + "</svg>"
    params = {
        "path": [{"x": 0, "y": 0, "z": 0}],
        "feed": 500,
        "text": "hello",
        "preview_svg": preview,
    }

    sanitized, error = validate_capability_params("write_text", params)

    assert error is None
    assert sanitized["preview_svg"].endswith("</svg>")
    assert len(sanitized["preview_svg"]) > 120


def test_validate_capability_params_accepts_control_capability_without_path():
    sanitized, error = validate_capability_params("home", {"source_capability": "home"})

    assert error is None
    assert sanitized == {"source_capability": "home"}


def test_capability_path_map_covers_active_capabilities():
    for cap in ("run_path", "write_text", "draw_generated", "home", "pause", "resume", "stop", "get_device_info"):
        assert cap in CAPABILITY_PATH_MAP
