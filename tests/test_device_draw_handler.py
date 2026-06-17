"""Unit tests for device_gateway.device_draw_handler."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Only stub xiaozhi_drawing submodules when the real ones are unavailable
# (e.g. cv2 not installed).  This avoids polluting sys.modules for the rest
# of the pytest session when the real modules *are* present.
_NEED_STUBS = False
try:
    import xiaozhi_drawing.svg_converter  # noqa: F401
    import xiaozhi_drawing.svg_validator  # noqa: F401
    import xiaozhi_drawing.path_optimizer  # noqa: F401
    import xiaozhi_drawing.preset_shapes  # noqa: F401
except (ImportError, ModuleNotFoundError):
    _NEED_STUBS = True

if _NEED_STUBS:
    from types import ModuleType as _MT

    _xiaozhi_drawing = _MT("xiaozhi_drawing")
    sys.modules.setdefault("xiaozhi_drawing", _xiaozhi_drawing)

    _stub_svg_converter = _MT("xiaozhi_drawing.svg_converter")
    _stub_svg_converter.SVGConverter = lambda: None
    sys.modules["xiaozhi_drawing.svg_converter"] = _stub_svg_converter

    _stub_svg_validator = _MT("xiaozhi_drawing.svg_validator")
    _stub_svg_validator.validate_svg_path = lambda *a, **k: None
    sys.modules["xiaozhi_drawing.svg_validator"] = _stub_svg_validator

    _stub_path_optimizer = _MT("xiaozhi_drawing.path_optimizer")
    _stub_path_optimizer.optimize_svg_path = lambda *a, **k: None
    sys.modules["xiaozhi_drawing.path_optimizer"] = _stub_path_optimizer

    _stub_preset_shapes = _MT("xiaozhi_drawing.preset_shapes")
    _stub_preset_shapes.get_preset_svg = lambda *a, **k: None
    sys.modules["xiaozhi_drawing.preset_shapes"] = _stub_preset_shapes

from device_gateway.device_draw_handler import (
    _build_failed_response,
    _build_partial_response,
    _build_success_response,
    _try_preset_shape,
    handle_device_draw,
)


class TestBuildResponses:
    def test_build_failed_response(self):
        resp = _build_failed_response("wanx2.1-t2i-turbo", "bad request")
        assert resp["status"] == "failed"
        assert resp["model"] == "wanx2.1-t2i-turbo"
        assert resp["error"] == "bad request"
        assert resp["svg_path"] is None

    def test_build_partial_response(self):
        resp = _build_partial_response("http://img", 100, 200, "m", "conv fail")
        assert resp["status"] == "partial"
        assert resp["image_url"] == "http://img"
        assert resp["width"] == 100
        assert resp["height"] == 200
        assert resp["svg_path"] is None
        assert resp["error"] == "conv fail"

    def test_build_success_response(self):
        svg_result = {"width": 100, "height": 200}
        optimization = SimpleNamespace(
            optimized_path="M0,0",
            original_points=100,
            optimized_points=50,
            reduction_ratio=0.5,
        )
        resp = _build_success_response("http://img", svg_result, optimization, "m")
        assert resp["status"] == "success"
        assert resp["image_url"] == "http://img"
        assert resp["svg_path"] == "M0,0"
        assert resp["optimization"]["reduction_ratio"] == 0.5


class TestPresetShape:
    @patch("device_gateway.device_draw_handler.get_preset_svg")
    def test_try_preset_shape_circle(self, mock_get):
        mock_get.return_value = {
            "status": "success",
            "svg_path": "M0,0",
            "width": 10,
            "height": 10,
        }
        resp = _try_preset_shape("画一个圆")
        assert resp is not None
        assert resp["status"] == "success"
        assert resp["model"] == "preset:circle"
        assert resp["preset"] is True

    @patch("device_gateway.device_draw_handler.get_preset_svg")
    def test_try_preset_shape_not_found(self, mock_get):
        mock_get.return_value = {"status": "error"}
        resp = _try_preset_shape("画一个圆")
        assert resp is None

    def test_try_preset_shape_no_keyword(self):
        resp = _try_preset_shape("hello world")
        assert resp is None


class TestHandleDeviceDraw:
    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p: f"enhanced {p}")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    @patch("device_gateway.device_draw_handler.optimize_svg_path")
    async def test_full_success_path(
        self,
        mock_optimize,
        mock_validate,
        mock_converter_cls,
        mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "status": "success",
            "images": [{"url": "http://img/1"}],
        }
        mock_client_cls.return_value = mock_client

        mock_converter = MagicMock()
        mock_converter.convert_url_to_svg = AsyncMock(
            return_value={"status": "success", "svg_path": "M0,0", "width": 100, "height": 200}
        )
        mock_converter_cls.return_value = mock_converter

        mock_validate.return_value = SimpleNamespace(valid=True, errors=[])
        mock_optimize.return_value = SimpleNamespace(
            optimized_path="M0,0",
            original_points=100,
            optimized_points=50,
            reduction_ratio=0.5,
        )

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "success"
        assert resp["image_url"] == "http://img/1"
        assert resp["svg_path"] == "M0,0"
        mock_client.generate.assert_called_once()

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_image_generation_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = {"status": "failed", "error": "rate limited"}
        mock_client_cls.return_value = mock_client

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "failed"
        assert resp["error"] == "rate limited"

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    async def test_svg_conversion_failure(self, mock_converter_cls, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "status": "success",
            "images": [{"url": "http://img/1"}],
        }
        mock_client_cls.return_value = mock_client

        mock_converter = MagicMock()
        mock_converter.convert_url_to_svg = AsyncMock(return_value={"status": "failed", "error": "cv2 missing"})
        mock_converter_cls.return_value = mock_converter

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "partial"
        assert "cv2 missing" in resp["error"]

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    async def test_svg_validation_failure(self, mock_validate, mock_converter_cls, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "status": "success",
            "images": [{"url": "http://img/1"}],
        }
        mock_client_cls.return_value = mock_client

        mock_converter = MagicMock()
        mock_converter.convert_url_to_svg = AsyncMock(
            return_value={"status": "success", "svg_path": "bad", "width": 100, "height": 200}
        )
        mock_converter_cls.return_value = mock_converter

        mock_validate.return_value = SimpleNamespace(valid=False, errors=["out of workspace"])

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "partial"
        assert "out of workspace" in resp["error"]

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_exception_path(self, mock_client_cls):
        mock_client_cls.side_effect = RuntimeError("boom")

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "failed"
        assert "boom" in resp["error"]
