"""Tests for dlc_core safety constants."""

from __future__ import annotations

from device_gateway.safety import DEFAULT_WORKSPACE_MM as GW_WORKSPACE
from dlc_core.safety import DEFAULT_WORKSPACE_MM, MAX_PATH_POINTS


def test_max_path_points_is_200() -> None:
    assert MAX_PATH_POINTS == 200


def test_default_workspace_mm_matches_product_canvas() -> None:
    # Single source of truth (device_intelligence.schemas); 300x300x80 is the
    # product writing-machine canvas — must not drift back to the old 100/20.
    assert DEFAULT_WORKSPACE_MM == {"x": 300.0, "y": 300.0, "z": 80.0}


def test_workspace_constant_is_single_sourced() -> None:
    """dlc_core and device_gateway must share one definition (regression guard)."""
    assert DEFAULT_WORKSPACE_MM is GW_WORKSPACE
