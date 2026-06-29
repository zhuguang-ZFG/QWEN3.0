"""Unit tests for device_gateway.device_draw_handler — error & edge cases."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from device_gateway.device_draw_handler import handle_device_draw
from device_gateway.draw_prompt_enhancer import reset_draw_prompt_history_for_tests
from session_memory.store import _get_conn, set_db_path


@pytest.fixture(autouse=True)
def _reset_draw_history(tmp_path):
    set_db_path(str(tmp_path / "device_draw_handler.db"))
    conn = _get_conn()
    conn.execute("DELETE FROM memories")
    conn.commit()
    conn.close()
    reset_draw_prompt_history_for_tests()
    yield
    reset_draw_prompt_history_for_tests()


class TestHandleDeviceDraw:
    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    @patch("device_gateway.device_draw_handler.optimize_svg_path")
    @patch("device_gateway.device_draw_handler.precheck_draw_motion_path")
    async def test_multi_turn_context_passed_on_second_draw(
        self,
        mock_precheck,
        mock_optimize,
        mock_validate,
        mock_converter_cls,
        mock_client_cls,
        mock_enhance,
    ):
        mock_enhance.return_value = "enhanced prompt"
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
            original_points=10,
            optimized_points=5,
            reduction_ratio=0.5,
        )
        mock_precheck.return_value = None

        await handle_device_draw("画一只猫", device_id="dev-multi")
        await handle_device_draw("再画大一点", device_id="dev-multi")

        second_call = mock_enhance.call_args_list[1]
        assert second_call.args[0] == "再画大一点"
        context = second_call.kwargs.get("conversation_context", "")
        assert "画一只猫" in context

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
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

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
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

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_exception_path(self, mock_client_cls):
        mock_client_cls.side_effect = RuntimeError("boom")

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "failed"
        assert "boom" in resp["error"]

    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    @patch("device_gateway.device_draw_handler.optimize_svg_path")
    @patch("device_gateway.device_draw_handler.precheck_draw_motion_path")
    async def test_provided_image_url_skips_generation(
        self,
        mock_precheck,
        mock_optimize,
        mock_validate,
        mock_converter_cls,
        mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_converter = MagicMock()
        mock_converter.convert_url_to_svg = AsyncMock(
            return_value={
                "status": "success",
                "svg_path": "M10,10",
                "width": 100,
                "height": 100,
                "skeleton_applied": False,
            }
        )
        mock_converter_cls.return_value = mock_converter

        mock_validate.return_value = SimpleNamespace(valid=True, errors=[])
        mock_optimize.return_value = SimpleNamespace(
            optimized_path="M10,10",
            original_points=10,
            optimized_points=5,
            reduction_ratio=0.5,
        )
        mock_precheck.return_value = None

        resp = await handle_device_draw("a cat", device_id="dev-img", image_url="https://example.com/cat.png")
        assert resp["status"] == "success"
        assert resp["image_url"] == "https://example.com/cat.png"
        mock_client.generate.assert_not_called()
        mock_converter.convert_url_to_svg.assert_awaited_once_with(
            "https://example.com/cat.png", skeletonize=True, reorder_strokes=True
        )
