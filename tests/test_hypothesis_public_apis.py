"""Hypothesis property tests for channel public APIs — calc, exchange, time."""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from channel_gateway.public_apis import fetch_calc, fetch_exchange, fetch_time


# ── calc ──

@given(
    a=st.integers(min_value=-999, max_value=999),
    b=st.integers(min_value=-999, max_value=999),
)
def test_calc_addition_commutes(a, b):
    left = fetch_calc(f"{a}+{b}")
    right = fetch_calc(f"{b}+{a}")
    assert left["ok"] and right["ok"]
    assert left["text"].split("=")[-1].strip() == right["text"].split("=")[-1].strip()


# ── exchange ──

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


# ── time ──

_KNOWN_TZ = st.sampled_from(
    ["Asia/Shanghai", "UTC", "America/New_York", "Europe/London", "Pacific/Auckland"]
)


@given(tz=_KNOWN_TZ)
def test_fetch_time_valid_timezone(tz):
    result = fetch_time(tz)
    assert result["ok"] is True
    assert tz in result["text"]
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result["text"])


def test_fetch_time_invalid_timezone_falls_back():
    result = fetch_time("Not/A_Real_Zone")
    assert result["ok"] is True
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result["text"])
