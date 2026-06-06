"""Tests for eval topology routing (M6: all cloud-native, FRP retired)."""

from __future__ import annotations

import pytest

import eval_topology


def test_needs_via_router_always_false_after_m6():
    """M6: LOCAL_ONLY_BACKENDS is empty — never needs FRP router."""
    assert eval_topology.needs_via_router("scnet_large_ds_flash") is False
    assert eval_topology.needs_via_router("kimi") is False
    assert eval_topology.needs_via_router("some_random") is False


def test_call_via_router_raises_after_m6():
    """M6: FRP path retired — call_via_router should raise OSError."""
    with pytest.raises(OSError, match="obsolete"):
        eval_topology.call_via_router(
            "scnet_large_ds_flash",
            [{"role": "user", "content": "hi"}],
            128,
            router_url="http://127.0.0.1:8088",
        )


def test_eval_via_router_disabled_after_m6():
    assert eval_topology.eval_via_router_enabled() is False
    assert eval_topology.eval_via_router_url() == ""
