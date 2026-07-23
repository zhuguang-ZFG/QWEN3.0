"""Tests for device_gateway.path_pipeline — text/SVG-to-path rendering."""

from device_gateway.path_data import PEN_UP_Z
from device_gateway.path_pipeline import (
    MAX_PATH_POINTS,
    preview_svg,
    render_svg_task,
    render_text_task,
    svg_path_to_motion,
    text_to_path,
)


def test_text_to_path_renders_ascii():
    path = text_to_path("Hi", origin_x=0, origin_y=20, scale=2)
    assert len(path) > 2
    assert all("x" in p and "y" in p and "z" in p for p in path)
    # Pen state is now written per point: z == 0 draws, z > 0 is pen-up travel.
    assert all(p["z"] in (0, PEN_UP_Z) for p in path)


def test_text_to_path_writes_pen_up_for_repositioning():
    # 'H' begins with a pen-up move to the first stroke start (font None marker).
    path = text_to_path("H", origin_x=0, origin_y=20, scale=2)
    pen_up = [p for p in path if p["z"] > 0]
    draw = [p for p in path if p["z"] == 0]
    assert pen_up, "expected at least one pen-up reposition point"
    assert all(p["z"] == PEN_UP_Z for p in pen_up)
    assert draw, "expected drawing points at z == 0"


def test_text_to_path_decimates_long_text_within_budget():
    # '写'*40 falls back to '?' glyphs (7 pts each = 280) — must decimate to
    # <= MAX_PATH_POINTS via per-stroke Douglas-Peucker, not silent truncation.
    path = text_to_path("写" * 40)
    assert 0 < len(path) <= MAX_PATH_POINTS
    # All 40 glyphs represented: x-span reflects full cursor advance, not a
    # truncated prefix.
    xs = [p["x"] for p in path]
    assert max(xs) - min(xs) > 100


def test_text_to_path_unknown_char_falls_back_to_question_mark():
    path = text_to_path("你好")  # Chinese "你好"
    assert len(path) > 0  # Renders as '?' glyphs instead of empty


def test_text_to_path_empty_text():
    path = text_to_path("")
    assert path == []


def test_text_to_path_clamps_bounds():
    path = text_to_path("A" * 80, origin_x=1000, origin_y=-500, scale=10)
    for pt in path:
        assert -200 <= pt["x"] <= 200
        assert -200 <= pt["y"] <= 200


def test_text_to_path_max_points():
    path = text_to_path("ABCDE" * 100)
    assert len(path) <= MAX_PATH_POINTS


def test_svg_path_to_motion_parses_m_l_z():
    path = svg_path_to_motion("M 10 10 L 50 10 L 50 50 Z", origin_x=0, origin_y=100, scale=1)
    # M 10 10 → L 50 10 → L 50 50 → Z back to 10 10
    assert len(path) >= 4


def test_svg_path_to_motion_parses_relative():
    path = svg_path_to_motion("m 10 10 l 40 0 l 0 40 z", origin_x=0, origin_y=100, scale=1)
    assert len(path) >= 4


def test_svg_path_to_motion_parses_cubic_bezier():
    path = svg_path_to_motion("M 10 10 C 20 30 40 30 50 10", origin_x=0, origin_y=100, scale=1)
    assert len(path) >= 2  # start point + bezier polyline approximation


def test_svg_path_to_motion_clamps_max_points():
    d = " ".join(f"M {i} {i} L {i + 1} {i + 1}" for i in range(300))
    path = svg_path_to_motion(d, max_points=50)
    assert len(path) <= 50


def test_preview_svg_generates_valid_svg():
    path = [{"x": 10, "y": 20, "z": 0}, {"x": 50, "y": 60, "z": 0}]
    svg = preview_svg(path, title="test path")
    assert "<svg" in svg
    assert "10,20" in svg
    assert "test path" in svg


def test_preview_svg_empty_path():
    svg = preview_svg([])
    assert "empty path" in svg


def test_render_text_task_returns_path_and_preview():
    result = render_text_task("LiMa")
    assert len(result["path"]) > 0
    assert "preview_svg" in result
    assert "LiMa" in result["preview_svg"]


def test_render_svg_task_returns_path_and_preview():
    result = render_svg_task("M 0 0 L 30 0 L 30 30 L 0 30 Z")
    assert len(result["path"]) >= 4
    assert "preview_svg" in result
