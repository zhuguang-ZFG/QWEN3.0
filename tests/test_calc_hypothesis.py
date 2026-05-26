"""Property tests for channel public calc helper."""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from channel_gateway.public_apis import fetch_calc


@given(
    a=st.integers(min_value=-999, max_value=999),
    b=st.integers(min_value=-999, max_value=999),
)
def test_calc_addition_commutes(a, b):
    left = fetch_calc(f"{a}+{b}")
    right = fetch_calc(f"{b}+{a}")
    assert left["ok"] and right["ok"]
    assert left["text"].split("=")[-1].strip() == right["text"].split("=")[-1].strip()
