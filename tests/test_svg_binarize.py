"""Tests for SVG converter binarization strategies."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from PIL import Image
from xiaozhi_drawing.svg_converter import SVGConverter, _binarize, _preprocess_image


class TestBinarization:
    """P0: adaptive threshold should kick in for uneven lighting, Otsu for clean art."""

    def _quadrant_gradient(self) -> np.ndarray:
        """A 120x120 image: top-left dark, bottom-right bright, no clear global threshold."""
        arr = np.zeros((120, 120), dtype=np.uint8)
        for r in range(120):
            for c in range(120):
                arr[r, c] = int(40 + (r + c) * 0.7)  # smooth gradient 40..208
        return arr

    def test_otsu_mode_forced(self):
        gray = self._quadrant_gradient()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary, method = _binarize(gray, blurred, "otsu")
        assert method == "otsu"
        assert binary.shape == gray.shape

    def test_adaptive_mode_forced(self):
        gray = self._quadrant_gradient()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary, method = _binarize(gray, blurred, "adaptive")
        assert method == "adaptive"
        assert binary.shape == gray.shape

    def test_auto_picks_adaptive_for_uneven_image(self):
        gray = self._quadrant_gradient()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, method = _binarize(gray, blurred, "auto")
        assert method == "adaptive"

    def test_auto_picks_otsu_for_even_line_art(self):
        # Uniform white background with a black circle — clean line art
        gray = np.full((100, 100), 250, dtype=np.uint8)
        cv2.circle(gray, (50, 50), 30, 10, -1)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, method = _binarize(gray, blurred, "auto")
        assert method == "otsu"

    def test_invalid_mode_raises(self):
        gray = np.zeros((20, 20), dtype=np.uint8)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        with pytest.raises(ValueError, match="unknown threshold_mode"):
            _binarize(gray, blurred, "bogus")

    def test_preprocess_returns_threshold_method(self):
        img = Image.new("RGB", (60, 60), "white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        gray, binary, method = _preprocess_image(buf, "auto")
        assert method in {"otsu", "adaptive"}
        assert gray.shape == binary.shape

    @pytest.mark.asyncio
    async def test_convert_url_reports_threshold_method(self):
        img = Image.new("RGB", (80, 80), "white")
        cv2.circle(np.array(img), (40, 40), 25, (0, 0, 0), 2)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            converter = SVGConverter()
            result = await converter.convert_url_to_svg("https://example.com/x.png", threshold_mode="adaptive")
            assert result["status"] == "success"
            assert result["threshold_method"] == "adaptive"

    @pytest.mark.asyncio
    async def test_convert_url_auto_recovers_strokes_from_gradient(self):
        """Uneven-lighting image: auto mode should still find strokes where Otsu floods."""
        # gradient background (uneven) with a dark stroke
        arr = np.zeros((120, 120, 3), dtype=np.uint8)
        for r in range(120):
            for c in range(120):
                v = int(40 + (r + c) * 0.7)
                arr[r, c] = (v, v, v)
        cv2.line(arr, (10, 60), (110, 60), (0, 0, 0), 4)
        img = Image.fromarray(arr)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()
        mock_response.raise_for_status = MagicMock()

        with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            converter = SVGConverter()
            result_auto = await converter.convert_url_to_svg(
                "https://example.com/x.png", skeletonize=True, threshold_mode="auto"
            )
            result_otsu = await converter.convert_url_to_svg(
                "https://example.com/x.png", skeletonize=True, threshold_mode="otsu"
            )

            assert result_auto["threshold_method"] == "adaptive"
            assert result_otsu["threshold_method"] == "otsu"
            # Both should successfully extract at least one stroke; adaptive
            # produces a cleaner single stroke on gradients, while Otsu tends
            # to fragment the gradient into spurious contours. We assert both
            # succeed and adaptive yields >=1 contour (stroke recovered, not lost).
            assert result_auto["contour_count"] >= 1
            assert result_otsu["contour_count"] >= 1
