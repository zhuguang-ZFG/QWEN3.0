"""Tests for context injection trace observability."""

from __future__ import annotations

import context_injection_trace as mod


def test_trace_records_and_summarizes():
    mod.begin_trace(scenario="coding", request_type="ide")
    mod.record_retrieval("x" * 100)
    mod.record_code_context("y" * 50)
    mod.record_memory_item("[code_fact]")
    mod.record_skills(["dir:python"])
    trace = mod.finish_trace(backend="scnet_ds_flash")
    assert trace is not None
    assert trace.retrieval_chars == 100
    assert trace.code_context_chars == 50
    meta = trace.to_meta()
    assert meta["memory_count"] == 1
    assert "skills" in meta
    recent = mod.get_recent_traces(limit=1)
    assert recent[0]["backend"] == "scnet_ds_flash"
