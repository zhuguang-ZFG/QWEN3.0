"""Hello workspace_mm requires all three axes (W4)."""

from __future__ import annotations

from device_gateway.device_profile.sources import _workspace_from_hello
from device_gateway.profiles import PRODUCT_WRITING_WORKSPACE_MM


def test_partial_workspace_falls_back_to_product():
    ws = _workspace_from_hello({"workspace_mm": {"x": 50.0}})
    assert ws["x"] == PRODUCT_WRITING_WORKSPACE_MM["x"]
    assert ws["y"] == PRODUCT_WRITING_WORKSPACE_MM["y"]


def test_complete_workspace_accepted():
    ws = _workspace_from_hello({"workspace_mm": {"x": 120.0, "y": 100.0, "z": 40.0}})
    assert ws == {"x": 120.0, "y": 100.0, "z": 40.0}
