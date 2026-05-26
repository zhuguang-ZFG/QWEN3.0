"""Hypothesis property tests for search_gateway.safety (radar §四)."""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from search_gateway.safety import redact_sensitive_query

_TOKEN = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"


@given(st.text(max_size=200))
def test_redact_never_leaks_injected_token(prefix: str):
    query = f"{prefix} token {_TOKEN} tail"
    redacted = redact_sensitive_query(query)
    assert _TOKEN not in redacted
    assert "[REDACTED_TOKEN]" in redacted or "token" in redacted


@given(st.sampled_from(["192.168.0.1", "10.0.0.1", "172.16.0.1", "172.31.255.255"]))
def test_redact_strips_known_private_ips(ip: str):
    redacted = redact_sensitive_query(f"host {ip} ok")
    assert ip not in redacted
    assert "[REDACTED_PRIVATE_IP]" in redacted
