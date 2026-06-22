"""Tests for session_memory.device_draw_memory persistence."""

from __future__ import annotations

import pytest

from session_memory.device_draw_memory import (
    DEVICE_DRAW_FAILED,
    list_device_draw_failures,
    record_device_draw_failure,
    reset_device_draw_failures,
)
from session_memory.store import _get_conn, query_by_type, set_db_path


@pytest.fixture(autouse=True)
def isolated_session_db(tmp_path):
    set_db_path(str(tmp_path / "device_draw_memory.db"))
    conn = _get_conn()
    conn.execute("DELETE FROM memories")
    conn.commit()
    conn.close()
    reset_device_draw_failures()
    yield
    reset_device_draw_failures()


def test_record_and_list_device_draw_failures():
    record_device_draw_failure("dev-1", "画一只猫", error="rate limited")
    prompts = list_device_draw_failures("dev-1")
    assert prompts == ["画一只猫"]

    entries = query_by_type(DEVICE_DRAW_FAILED, session_id="device:dev-1")
    assert len(entries) == 1
    assert entries[0].summary == "画一只猫"
    assert "rate limited" in entries[0].detail


def test_prunes_old_entries_beyond_limit():
    for idx in range(7):
        record_device_draw_failure("dev-2", f"prompt-{idx}")
    assert list_device_draw_failures("dev-2") == [
        "prompt-2",
        "prompt-3",
        "prompt-4",
        "prompt-5",
        "prompt-6",
    ]
    entries = query_by_type(DEVICE_DRAW_FAILED, session_id="device:dev-2")
    assert len(entries) == 5
