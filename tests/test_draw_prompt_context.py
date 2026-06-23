"""Tests for device_gateway.draw_prompt_enhancer context helpers."""

from __future__ import annotations

import pytest

from device_gateway.device_profile.models import DeviceCapability, DeviceProfile
from device_gateway.device_profile.registry import register_device_profile, reset_device_profiles_for_tests
from device_gateway.draw_prompt_enhancer import (
    get_failed_draw_prompts,
    record_failed_draw_prompt,
    reset_draw_prompt_history_for_tests,
    resolve_device_type,
)
from session_memory.store import _get_conn, set_db_path


@pytest.fixture(autouse=True)
def isolated_session_db(tmp_path):
    set_db_path(str(tmp_path / "draw_prompt_context.db"))
    conn = _get_conn()
    conn.execute("DELETE FROM memories")
    conn.commit()
    conn.close()
    reset_device_profiles_for_tests()
    reset_draw_prompt_history_for_tests()
    yield
    reset_draw_prompt_history_for_tests()
    reset_device_profiles_for_tests()


def test_resolve_device_type_from_prefs_override():
    assert resolve_device_type("dev-1", {"device_type": "esp32_writing_machine"}) == "esp32_writing_machine"


def test_resolve_device_type_from_profile_model():
    register_device_profile(DeviceProfile(device_id="dev-u8", model="U8-writing"))
    assert resolve_device_type("dev-u8", {}) == "esp32_writing_machine"


def test_resolve_device_type_defaults_to_plotter():
    register_device_profile(DeviceProfile(device_id="dev-1", model="U1-plotter"))
    assert resolve_device_type("dev-1", {}) == "esp32_xy_plotter"


def test_failed_prompt_history_roundtrip():
    record_failed_draw_prompt("dev-1", "过于复杂的森林", error="svg failed")
    assert get_failed_draw_prompts("dev-1") == ["过于复杂的森林"]


def test_failed_prompt_history_caps_entries():
    for idx in range(7):
        record_failed_draw_prompt("dev-1", f"prompt-{idx}")
    history = get_failed_draw_prompts("dev-1")
    assert len(history) == 5
    assert history[0] == "prompt-2"
    assert history[-1] == "prompt-6"


def test_failed_prompt_history_persists_across_reads():
    record_failed_draw_prompt("dev-persist", "一只复杂的龙")
    first = get_failed_draw_prompts("dev-persist")
    second = get_failed_draw_prompts("dev-persist")
    assert first == second == ["一只复杂的龙"]


def test_get_draw_conversation_context_from_turns():
    from device_gateway.draw_prompt_enhancer import get_draw_conversation_context, record_device_draw_turn

    record_device_draw_turn("dev-ctx", "画一只猫", status="success")
    context = get_draw_conversation_context("dev-ctx", "再画大一点")
    assert "画一只猫" in context
