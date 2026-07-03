"""Tests for device command safety hardening.

Covers:
- Capability whitelist validation in _llm_replan
- Dangerous capability rejection
- Unknown capability rejection
"""

import json


import http_caller
import device_gateway.intent as dgi


# ── Helpers ───────────────────────────────────────────────────────────────

ALLOWED = frozenset(
    {
        "home",
        "pause",
        "resume",
        "stop",
        "get_device_info",
        "write_text",
        "draw_generated",
        "run_path",
        "move_abs",
        "move_rel",
    }
)

DANGEROUS = frozenset(
    {
        "spindle_on",
        "laser_on",
        "heater_on",
        "gpio_high",
        "m3",
        "m4",
        "m8",
        "spindle_cw",
        "spindle_ccw",
    }
)


def _mock_llm_call(monkeypatch, response_json: dict):
    """Monkeypatch http_caller.call_api to return a canned JSON response."""

    def fake_call(*args, **kwargs):
        return json.dumps(response_json)

    monkeypatch.setattr(http_caller, "call_api", fake_call)


# ── Capability whitelist ─────────────────────────────────────────────────


def test_allowed_capabilities_include_safe_operations():
    """Verify the whitelist contains expected safe capabilities."""
    for cap in ("home", "stop", "write_text", "draw_generated", "move_abs"):
        assert cap in ALLOWED


def test_dangerous_capabilities_not_in_allowed():
    """Dangerous capabilities must not be in the allowed set."""
    assert not ALLOWED.intersection(DANGEROUS)


def test_llm_replan_rejects_dangerous_capability(monkeypatch):
    """LLM replan must reject a dangerous capability returned by the model."""
    _mock_llm_call(monkeypatch, {"capability": "spindle_on", "params": {}, "reason": "evil"})
    result = dgi._llm_replan("spin up", {"capability": "unknown"})
    assert result is None or result.get("capability") != "spindle_on"
    if result:
        assert result["capability"] in ("rejected", "write_text")


def test_llm_replan_rejects_unknown_capability(monkeypatch):
    """LLM replan must reject a capability not in the whitelist."""
    _mock_llm_call(monkeypatch, {"capability": "delete_everything", "params": {}})
    result = dgi._llm_replan("format the machine", {"capability": "unknown"})
    assert result is None or result.get("capability") != "delete_everything"
    if result:
        assert result["capability"] in ("rejected", "write_text")


def test_llm_replan_accepts_allowed_capability(monkeypatch):
    """LLM replan must accept a capability that is in the whitelist."""
    _mock_llm_call(monkeypatch, {"capability": "stop", "params": {}})
    result = dgi._llm_replan("stop now", {"capability": "unknown"})
    assert result is not None
    assert result["capability"] == "stop"


def test_llm_planner_lives_in_dedicated_module_and_is_re_exported():
    """Lock the T-batch extraction: the LLM planner sub-domain (4 functions +
    2 capability sets) lives in ``device_gateway.intent_llm_planner`` yet stays
    importable from ``device_gateway.intent`` for prod (prompt_engineering.layers
    reads DANGEROUS_CAPABILITIES) and tests (dgi._llm_replan is patched/called).
    Guards against accidental re-export loss during the split.
    """
    from device_gateway import intent_llm_planner as planner

    # The planner sub-domain owns the four functions and both capability sets.
    assert callable(planner._llm_replan)
    assert callable(planner._interpret_llm_plan)
    assert callable(planner._build_llm_planner_prompt)
    assert callable(planner._strip_code_fence)
    assert "spindle_on" in planner.DANGEROUS_CAPABILITIES
    assert "write_text" in planner._ALLOWED_CAPABILITIES

    # intent.py re-exports the prod-facing set and the test-facing function
    # (same object identity — a re-export, not a copy).
    assert dgi.DANGEROUS_CAPABILITIES is planner.DANGEROUS_CAPABILITIES
    assert dgi._llm_replan is planner._llm_replan
