"""Unit tests for the fake U1 route_policy validator.

The validator lives in the esp32S_XYZ product submodule; these tests make sure
LiMa's cloud rejections align with the firmware-side contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ESP32_TOOLS = Path(__file__).resolve().parent.parent / "esp32S_XYZ" / "tools"
sys.path.insert(0, str(_ESP32_TOOLS / "fake_u1"))

from route_policy_validator import validate_route_policy_for_u1


def test_valid_device_write_policy_passes():
    policy = {
        "route_role": "device_write",
        "primary_strategy": "provided_path",
        "artifact_required": "vector_path",
        "backend": "dashscope_wanx",
    }
    ok, code, message = validate_route_policy_for_u1(policy, fw_capabilities={"run_path"})
    assert ok is True
    assert code == ""
    assert message == ""


def test_missing_route_policy_rejected():
    ok, code, message = validate_route_policy_for_u1(None)
    assert ok is False
    assert code == "E009"
    assert "missing" in message


def test_unknown_route_role_rejected():
    policy = {"route_role": "fly_to_moon", "primary_strategy": "deterministic", "artifact_required": "none"}
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "route_role" in message


def test_unknown_primary_strategy_rejected():
    policy = {"route_role": "device_control", "primary_strategy": "magic", "artifact_required": "none"}
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "primary_strategy" in message


def test_unknown_artifact_required_rejected():
    policy = {"route_role": "device_control", "primary_strategy": "deterministic", "artifact_required": "gcode"}
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "artifact_required" in message


def test_unknown_backend_rejected():
    policy = {
        "route_role": "device_draw",
        "primary_strategy": "image_then_vector",
        "artifact_required": "preview_svg",
        "backend": "unsupported_backend",
    }
    ok, code, message = validate_route_policy_for_u1(policy, fw_capabilities={"run_path"})
    assert ok is False
    assert code == "E009"
    assert "backend" in message


def test_incompatible_strategy_for_role_rejected():
    policy = {"route_role": "device_control", "primary_strategy": "image_then_vector", "artifact_required": "none"}
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "strategy" in message


def test_incompatible_artifact_for_role_rejected():
    policy = {"route_role": "device_control", "primary_strategy": "deterministic", "artifact_required": "preview_svg"}
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "artifact" in message


def test_device_draw_requires_run_path_capability():
    policy = {
        "route_role": "device_draw",
        "primary_strategy": "image_then_vector",
        "artifact_required": "preview_svg",
    }
    ok, code, message = validate_route_policy_for_u1(policy, fw_capabilities={"device_info"})
    assert ok is False
    assert code == "E009"
    assert "run_path" in message


def test_device_control_cannot_require_model():
    policy = {
        "route_role": "device_control",
        "primary_strategy": "deterministic",
        "artifact_required": "none",
        "model_required": True,
    }
    ok, code, message = validate_route_policy_for_u1(policy)
    assert ok is False
    assert code == "E009"
    assert "model" in message
