"""Tests for device_gateway.draw_path_bounds (Tabbit L3)."""

from __future__ import annotations

from unittest.mock import patch

from device_gateway.path_pipeline import precheck_draw_motion_path


def test_precheck_accepts_simple_path():
    err = precheck_draw_motion_path("M 10 10 L 50 50")
    assert err is None


def test_precheck_rejects_empty_svg():
    assert precheck_draw_motion_path("") == "empty svg path"
    assert precheck_draw_motion_path("   ") == "empty svg path"


@patch("device_gateway.path_pipeline.render_svg_task")
def test_precheck_rejects_empty_motion(mock_render):
    mock_render.return_value = {"path": [], "point_count": 0}
    assert precheck_draw_motion_path("M0,0") == "empty motion path"


@patch("device_gateway.path_pipeline.render_svg_task")
def test_precheck_rejects_out_of_bounds_point(mock_render):
    mock_render.return_value = {
        "path": [{"x": 350.0, "y": 50.0, "z": 0.0}],
        "point_count": 1,
        "workspace_mm": {"x": 300.0, "y": 300.0, "z": 80.0},
    }
    err = precheck_draw_motion_path("M0,0")
    assert err is not None
    assert "outside workspace" in err
    assert "350" in err
