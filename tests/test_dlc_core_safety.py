"""Tests for dlc_core safety constants."""

from __future__ import annotations

from dlc_core.safety import DEFAULT_WORKSPACE_MM, MAX_PATH_POINTS


def test_max_path_points_is_200() -> None:
    assert MAX_PATH_POINTS == 200


def test_default_workspace_mm() -> None:
    assert DEFAULT_WORKSPACE_MM == {"x": 100.0, "y": 100.0, "z": 20.0}
