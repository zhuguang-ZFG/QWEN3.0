"""Tests for svg_converter skeleton / single-stroke pipeline."""

from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from xiaozhi_drawing.skeleton_tracer import polylines_to_svg_paths, trace_skeleton_polylines
from xiaozhi_drawing.svg_converter import (  # noqa: E402
    SVGConverter,
    _contour_to_svg_path,
    _extract_svg_paths,
    _thin_binary,
    _thin_morphological,
)


def _horizontal_line_binary(width: int = 40, height: int = 20, thickness: int = 5) -> np.ndarray:
    binary = np.zeros((height, width), dtype=np.uint8)
    y0 = height // 2 - thickness // 2
    binary[y0 : y0 + thickness, :] = 255
    return binary


def _plus_skeleton(size: int = 11) -> np.ndarray:
    skeleton = np.zeros((size, size), dtype=np.uint8)
    mid = size // 2
    skeleton[mid, 2 : size - 2] = 255
    skeleton[2 : size - 2, mid] = 255
    return skeleton


class TestSkeletonTracer:
    def test_trace_horizontal_line(self):
        skeleton = np.zeros((5, 20), dtype=np.uint8)
        skeleton[2, :] = 255
        polylines = trace_skeleton_polylines(skeleton)
        assert len(polylines) == 1
        assert len(polylines[0]) >= 2

    def test_trace_plus_has_multiple_strokes(self):
        polylines = trace_skeleton_polylines(_plus_skeleton())
        assert len(polylines) >= 2

    def test_trace_empty_returns_empty(self):
        assert trace_skeleton_polylines(np.zeros((8, 8), dtype=np.uint8)) == []

    def test_polylines_to_svg_open_paths(self):
        polylines = [[(0, 0), (10, 0), (10, 10)]]
        paths = polylines_to_svg_paths(polylines, simplify_epsilon=1.0, min_arc_length=1.0)
        assert len(paths) == 1
        assert " Z" not in paths[0]
        assert paths[0].startswith("M ")


class TestThinMorphological:
    def test_reduces_pixel_count(self):
        binary = _horizontal_line_binary()
        thinned = _thin_morphological(binary)
        assert cv2.countNonZero(thinned) < cv2.countNonZero(binary)

    def test_preserves_connectivity(self):
        binary = _horizontal_line_binary()
        thinned = _thin_morphological(binary)
        assert cv2.countNonZero(thinned) > 0

    def test_narrows_column_width(self):
        binary = _horizontal_line_binary(thickness=7)
        thinned = _thin_morphological(binary)
        cols = np.where(thinned.any(axis=0))[0]
        assert cols.size > 0
        active_rows = [np.where(thinned[:, c])[0] for c in cols[::5]]
        max_span = max((rows.max() - rows.min() + 1) for rows in active_rows if rows.size)
        assert max_span <= 3


class TestThinBinary:
    def test_returns_same_shape(self):
        binary = _horizontal_line_binary()
        thinned, method = _thin_binary(binary)
        assert thinned.shape == binary.shape
        assert method in {"skimage", "ximgproc", "morphological"}

    def test_result_is_thinner(self):
        binary = _horizontal_line_binary(thickness=7)
        thinned, _ = _thin_binary(binary)
        assert cv2.countNonZero(thinned) <= cv2.countNonZero(binary)

    def test_does_not_erase_line(self):
        binary = _horizontal_line_binary()
        thinned, _ = _thin_binary(binary)
        assert cv2.countNonZero(thinned) > 0


class TestContourToSvgPath:
    def test_closed_path_has_z(self):
        contour = np.array([[[0, 0]], [[10, 0]], [[10, 10]]], dtype=np.int32)
        path = _contour_to_svg_path(contour, closed=True)
        assert path.endswith(" Z")
        assert "M 0 0" in path

    def test_open_path_has_no_z(self):
        contour = np.array([[[0, 0]], [[10, 0]], [[10, 10]]], dtype=np.int32)
        path = _contour_to_svg_path(contour, closed=False)
        assert " Z" not in path
        assert "L 10 0" in path

    def test_empty_contour_returns_empty(self):
        contour = np.empty((0, 1, 2), dtype=np.int32)
        assert _contour_to_svg_path(contour) == ""

    def test_includes_all_points(self):
        contour = np.array([[[1, 2]], [[3, 4]], [[5, 6]]], dtype=np.int32)
        path = _contour_to_svg_path(contour, closed=False)
        assert "M 1 2" in path
        assert "L 3 4" in path
        assert "L 5 6" in path


class TestExtractSvgPaths:
    def test_legacy_mode_uses_closed_paths(self):
        binary = _horizontal_line_binary()
        paths, method = _extract_svg_paths(binary, simplify_epsilon=1.0, min_contour_area=1, skeletonize=False)
        assert paths
        assert method is None
        assert any(" Z" in path for path in paths)

    def test_skeleton_mode_uses_open_paths(self):
        binary = _horizontal_line_binary()
        paths, method = _extract_svg_paths(binary, simplify_epsilon=1.0, min_contour_area=1, skeletonize=True)
        assert paths
        assert method in {"skimage", "ximgproc", "morphological"}
        assert all(" Z" not in path for path in paths)

    def test_empty_image_returns_empty_list(self):
        binary = np.zeros((20, 20), dtype=np.uint8)
        paths, method = _extract_svg_paths(binary, 1.0, 1, skeletonize=True)
        assert paths == []
        assert method in {"skimage", "ximgproc", "morphological"}


class TestSVGConverterParams:
    @pytest.mark.asyncio
    async def test_default_skeletonize_is_false(self):
        converter = SVGConverter()
        from unittest.mock import AsyncMock, MagicMock, patch
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGB", (40, 20), "white")
        pixels = np.array(img)
        pixels[9:11, :] = 0
        img = Image.fromarray(pixels)
        buf = BytesIO()
        img.save(buf, format="PNG")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("xiaozhi_drawing.svg_converter._extract_svg_paths") as mock_extract:
                mock_extract.return_value = (["M 0 0 L 1 1"], None)
                result = await converter.convert_url_to_svg("https://example.com/x.png")
                assert mock_extract.call_args.kwargs.get("skeletonize") is False
                assert result["skeleton_applied"] is False
                assert result["thinning_method"] is None

    @pytest.mark.asyncio
    async def test_skeletonize_true_is_reflected_in_response(self):
        converter = SVGConverter()
        from unittest.mock import AsyncMock, MagicMock, patch
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGB", (40, 20), "white")
        buf = BytesIO()
        img.save(buf, format="PNG")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("xiaozhi_drawing.svg_converter._extract_svg_paths") as mock_extract:
                mock_extract.return_value = (["M 0 0 L 1 1"], "skimage")
                result = await converter.convert_url_to_svg("https://example.com/x.png", skeletonize=True)
                assert mock_extract.call_args.kwargs.get("skeletonize") is True
                assert result["skeleton_applied"] is True
                assert result["thinning_method"] == "skimage"

    @pytest.mark.asyncio
    async def test_skeletonize_empty_paths_returns_failed(self):
        converter = SVGConverter()
        from unittest.mock import AsyncMock, MagicMock, patch
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGB", (40, 20), "white")
        buf = BytesIO()
        img.save(buf, format="PNG")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("xiaozhi_drawing.svg_converter._extract_svg_paths") as mock_extract:
                mock_extract.return_value = ([], "skimage")
                result = await converter.convert_url_to_svg("https://example.com/x.png", skeletonize=True)
                assert result["status"] == "failed"
                assert result["skeleton_applied"] is True
                assert "No stroke paths" in result["error"]
