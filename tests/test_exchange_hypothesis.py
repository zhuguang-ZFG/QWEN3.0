"""Property tests for channel exchange helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from channel_gateway.public_apis import fetch_exchange

_RATE = 7.25


def _fake_rates(_url: str) -> dict:
    return {"rates": {"CNY": _RATE}, "date": "2026-05-26"}


@given(amount=st.floats(min_value=0.01, max_value=9999.0, allow_nan=False, allow_infinity=False))
def test_exchange_amount_scales_linearly(amount):
    with patch("channel_gateway.public_apis._get_json", side_effect=_fake_rates):
        result = fetch_exchange("USD", "CNY", amount)
    assert result["ok"] is True
    expected = round(amount * _RATE, 4)
    assert str(expected) in result["text"]
    assert "USD" in result["text"] and "CNY" in result["text"]
