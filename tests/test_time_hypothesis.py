"""Property tests for channel time helper."""

from __future__ import annotations

import re

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from channel_gateway.public_apis import fetch_time

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
    assert "Not/A_Real_Zone" in result["text"]
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result["text"])
