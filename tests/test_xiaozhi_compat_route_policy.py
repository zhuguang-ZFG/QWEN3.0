"""[DEPRECATED v3.1] Tests for retired XiaoZhi v1 compatibility layer.
Kept for reference only; do not extend."""


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routes.xiaozhi_compat.gateway import build_gateway_task  # noqa: E402

_VALID_ROLES = {
    "device_control",
    "device_write",
    "device_draw",
    "device_vector",
    "device_unknown",
}
_VALID_STRATEGIES = {
    "deterministic",
    "image_then_vector",
    "svg_vector",
    "provided_path",
    "planner_required",
}
_VALID_ARTIFACTS = {"none", "preview_svg", "vector_path"}


def _assert_valid_route_policy(policy):
    assert isinstance(policy, dict)
    assert policy["route_role"] in _VALID_ROLES
    assert isinstance(policy["model_required"], bool)
    assert policy["primary_strategy"] in _VALID_STRATEGIES
    assert policy["artifact_required"] in _VALID_ARTIFACTS


def test_run_path_task_has_device_vector_route_policy():
    task, err = build_gateway_task(
        device_id="dev-1",
        intent="run_path",
        params={"path": [{"x": 0, "y": 0}, {"x": 10, "y": 10}], "feed": 600},
        source="client",
        request_id="req-1",
    )
    assert err is None, f"unexpected error: {err}"
    assert task is not None
    _assert_valid_route_policy(task["route_policy"])
    assert task["route_policy"]["route_role"] == "device_vector"


def test_home_task_has_device_control_route_policy():
    task, err = build_gateway_task(
        device_id="dev-1",
        intent="home",
        params={},
        source="client",
        request_id="req-2",
    )
    assert err is None, f"unexpected error: {err}"
    assert task is not None
    _assert_valid_route_policy(task["route_policy"])
    assert task["route_policy"]["route_role"] == "device_control"
    assert task["route_policy"]["primary_strategy"] == "deterministic"
