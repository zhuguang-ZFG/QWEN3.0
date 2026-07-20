"""Regression tests for GW-WH (2026-07-20 round-2 review).

Voice-layer emergency stop: 急停/估停/estop/emergency must resolve to the
estop control command with top priority, and unknown low-confidence speech
must be rejected instead of falling back to a write_text motion task.
"""

from __future__ import annotations

import pytest

from device_gateway.intent import parse_command, resolve_voice_task


def test_estop_exact_match_has_full_confidence():
    result = parse_command("急停")
    assert result["capability"] == "estop"
    assert result["confidence"] == 1.0


@pytest.mark.parametrize(
    "text",
    [
        "急停",
        "紧急停止",
        "估停",  # common ASR mishearing of 急停
        "estop",
        "e-stop",
        "e stop",
        "emergency",
        "emergency stop",
        "EMERGENCY STOP",
        "快急停",  # emergency keyword embedded in a longer utterance
        "马上急停啊",
    ],
)
def test_emergency_stop_variants_map_to_estop(text):
    assert parse_command(text)["capability"] == "estop"


def test_emergency_keyword_outranks_draw_pattern():
    # Even a draw-like phrase containing 急停 must stop, never move the pen.
    assert parse_command("画完之前急停")["capability"] == "estop"


@pytest.mark.parametrize("text", ["停", "停下", "停下来", "快停", "停止", "stop"])
def test_plain_stop_words_map_to_stop(text):
    result = parse_command(text)
    assert result["capability"] == "stop"
    assert result["confidence"] == 1.0


def test_unknown_command_is_rejected_without_motion_params():
    result = parse_command("给我讲个笑话")
    assert result["capability"] == "rejected"
    assert result["confidence"] < 0.5
    assert result["params"] == {}


def test_empty_command_is_rejected():
    result = parse_command("")
    assert result["capability"] == "rejected"
    assert result["params"] == {}


def test_resolve_voice_task_estop_and_rejection():
    assert resolve_voice_task("急停")["capability"] == "estop"
    assert resolve_voice_task("随便聊聊天气")["capability"] == "rejected"


def test_normal_commands_unaffected_by_estop_priority():
    assert parse_command("写你好")["capability"] == "write_text"
    assert parse_command("画一个星星")["capability"] == "draw_generated"
    assert parse_command("home")["capability"] == "home"


# ── GW-R3-8: LLM replanner must not upgrade a rejection into pen motion ───────


def test_llm_replan_cannot_turn_rejected_into_motion(monkeypatch):
    """GW-R3-8/GW-WH: an unrecognized (rejected) utterance must never be
    replanned into a motion capability, even with the LLM planner enabled."""
    from config.settings import FLAGS
    import device_gateway.intent as intent

    monkeypatch.setattr(FLAGS, "device_llm_planner", True, raising=False)

    def _fake_replan(_text, _fallback):
        return {"capability": "draw_generated", "params": {"prompt": "cat"}, "source": "llm"}

    monkeypatch.setattr(intent, "_llm_replan", _fake_replan)
    result = intent.resolve_voice_task("some unrecognized utterance")
    # The motion replan is refused; the original rejection stands.
    assert result["capability"] == "rejected"


def test_llm_replan_may_turn_rejected_into_control(monkeypatch):
    """GW-R3-8: replanning a rejected command into a control capability
    (stop/pause/home/...) is still permitted — only motion is blocked."""
    from config.settings import FLAGS
    import device_gateway.intent as intent

    monkeypatch.setattr(FLAGS, "device_llm_planner", True, raising=False)

    def _fake_replan(_text, _fallback):
        return {"capability": "stop", "params": {}, "source": "llm"}

    monkeypatch.setattr(intent, "_llm_replan", _fake_replan)
    result = intent.resolve_voice_task("some unrecognized utterance")
    assert result["capability"] == "stop"
