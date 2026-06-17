"""Tests that route_policy carries a backend field.

Guards the stage-2 sub-project #5 contract: resolve_device_route_policy must
attach the selected backend to route_policy. With the field present,
tasks.py:135 `route_policy.get("backend", "unknown")` resolves to the real
backend instead of 'unknown' whenever the sticky-routing gate passes.
See spec docs/superpowers/specs/2026-06-15-route-policy-backend-field-design.md.
"""

from device_gateway.model_routing import resolve_device_route_policy


def test_resolve_includes_backend_for_all_capability_families():
    # Covers each route_role branch in resolve_device_route_policy.
    cases = [
        ({"capability": "home", "params": {}}, "device_control"),
        ({"capability": "write_text", "params": {"text": "LiMa"}}, "device_write"),
        ({"capability": "draw_generated", "params": {"prompt": "画一只猫"}}, "device_draw"),
        ({"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}}, "device_vector"),
        ({"capability": "run_path", "params": {}}, "device_vector"),
        ({"capability": "totally_unknown_capability", "params": {}}, "device_unknown"),
    ]
    for voice_task, expected_role in cases:
        policy = resolve_device_route_policy(voice_task)
        assert policy["route_role"] == expected_role
        assert "backend" in policy, f"backend key missing for {voice_task['capability']}"
        assert policy["backend"] != "", f"backend empty for {voice_task['capability']}"


def test_backend_matches_device_role_preferences():
    # Real backend for device_draw.
    assert (
        resolve_device_route_policy({"capability": "draw_generated", "params": {"prompt": "画一只猫"}})["backend"]
        == "dashscope_wanx"
    )
    # Local markers for the deterministic/local roles.
    assert (
        resolve_device_route_policy({"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}})["backend"]
        == "opencv_contour"
    )
    assert resolve_device_route_policy({"capability": "run_path", "params": {}})["backend"] == "opencv_contour"
    assert resolve_device_route_policy({"capability": "home", "params": {}})["backend"] == "deterministic"


def test_resolve_never_returns_unknown_as_backend():
    """Regression guard: the old fallback was 'unknown' at the call site.
    The policy itself must carry a concrete backend value, never the literal
    'unknown' (that was the symptom of the missing field, not a valid value).
    """
    for capability in ("home", "write_text", "draw_generated", "run_path", "nope"):
        policy = resolve_device_route_policy({"capability": capability, "params": {"prompt": "cat"}})
        assert policy["backend"] != "unknown", (
            f"resolve returned backend='unknown' for {capability}; the backend-field gap is not closed"
        )


def test_policy_factory_includes_backend_with_default():
    """_policy() must accept an optional backend and default to empty string,
    so existing direct callers that omit it do not break."""
    from device_gateway.model_routing import _policy

    full = _policy("device_draw", True, "image_then_vector", "vector_path", "dashscope_wanx")
    assert full["backend"] == "dashscope_wanx"
    default = _policy("device_control", False, "deterministic", "none")
    assert default["backend"] == ""
