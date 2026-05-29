"""Unit tests for channel public API helpers (no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_gateway import public_apis


class TestFetchCalc:
    def test_basic_arithmetic(self):
        r = public_apis.fetch_calc("1+2*3")
        assert r["ok"]
        assert "7" in r["text"]

    def test_rejects_invalid_chars(self):
        r = public_apis.fetch_calc("import os")
        assert not r["ok"]
