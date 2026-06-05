"""Tests for tool repair pipeline (Scavenge + Truncation + Storm)."""

from __future__ import annotations

import json

from tool_repair_pipeline import repair_tool_calls_from_text, storm_breaker


def test_scavenge_dsml_tool_call():
    text = (
        '<tool_call>{"name": "read_file", "arguments": {"path": "a.py"}}</tool_call>'
    )
    cleaned, calls, meta = repair_tool_calls_from_text(text)
    assert calls
    assert calls[0]["function"]["name"] == "read_file"
    assert meta["scavenge"] >= 1


def test_truncation_repair_closes_json():
    text = '{"name": "write_file", "arguments": {"path": "b.py", "content": "hi"'
    cleaned, calls, meta = repair_tool_calls_from_text(text)
    assert calls
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["path"] == "b.py"


def test_storm_breaker_drops_repeats():
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"path":"x"}'},
    }
    repeated = [call] * 5
    out, storm = storm_breaker(repeated, max_repeat=2)
    assert storm is True
    assert len(out) == 2
