"""Unit tests for device_gateway.device_draw_handler."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from device_gateway.device_draw_handler import (
    _build_failed_response,
    _build_partial_response,
    _build_success_response,
    _try_preset_shape,
    handle_device_draw,
)
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


class TestBuildResponses:
    def test_build_failed_response(self):
        resp = _build_failed_response("wanx2.1-t2i-turbo", "bad request")
        assert resp["status"] == "failed"
        # 对外统一返回品牌标签「LiMa 生图」，真实模型名（wanx2.1-t2i-turbo）不外泄。
        assert resp["model"] == "LiMa 生图"
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
        with patch("device_gateway.device_draw_handler.precheck_draw_motion_path", return_value=None):
            resp = _try_preset_shape("画一个圆")
        assert resp is not None
        assert resp["status"] == "success"
        assert resp["model"] == "preset:circle"
        assert resp["preset"] is True

    @patch("device_gateway.device_draw_handler.get_preset_svg")
    def test_try_preset_shape_bounds_failure(self, mock_get):
        mock_get.return_value = {
            "status": "success",
            "svg_path": "M0,0",
            "width": 10,
            "height": 10,
        }
        with patch(
            "device_gateway.device_draw_handler.precheck_draw_motion_path",
            return_value="motion point 0 (150,50,0) outside workspace 100x100mm",
        ):
            resp = _try_preset_shape("画一个圆")
        assert resp is not None
        assert resp["status"] == "failed"
        assert "Motion bounds precheck failed" in resp["error"]

    @patch("device_gateway.device_draw_handler.get_preset_svg")
    def test_try_preset_shape_not_found(self, mock_get):
        mock_get.return_value = {"status": "error"}
        resp = _try_preset_shape("画一个圆")
        assert resp is None

    def test_try_preset_shape_no_keyword(self):
        resp = _try_preset_shape("hello world")
        assert resp is None


class TestHandleDeviceDraw:
    def _setup_full_success_mocks(
        self,
        mock_enhance,
        mock_client_cls,
        mock_converter_cls,
        mock_validate,
        mock_optimize,
        mock_precheck,
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
            return_value={
                "status": "success",
                "svg_path": "M0,0",
                "width": 100,
                "height": 200,
                "skeleton_applied": True,
                "thinning_method": "skimage",
            }
        )
        mock_converter_cls.return_value = mock_converter

        mock_validate.return_value = SimpleNamespace(valid=True, errors=[])
        mock_optimize.return_value = SimpleNamespace(
            optimized_path="M0,0",
            original_points=100,
            optimized_points=50,
            reduction_ratio=0.5,
        )
        mock_precheck.return_value = None
        return mock_client, mock_converter

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    @patch("device_gateway.device_draw_handler.optimize_svg_path")
    @patch("device_gateway.device_draw_handler.precheck_draw_motion_path")
    async def test_full_success_path(
        self,
        mock_precheck,
        mock_optimize,
        mock_validate,
        mock_converter_cls,
        mock_client_cls,
        mock_enhance,
    ):
        mock_client, mock_converter = self._setup_full_success_mocks(
            mock_enhance, mock_client_cls, mock_converter_cls, mock_validate, mock_optimize, mock_precheck
        )

        resp = await handle_device_draw(
            "a cat", device_id="dev-1", user_preferences={"style": "可爱", "complexity": "低"}
        )
        assert resp["status"] == "success"
        mock_enhance.assert_called_once_with(
            "a cat",
            style="可爱",
            complexity="低",
            device_type="esp32_xy_plotter",
            previous_failed_prompts=None,
            conversation_context="",
            device_profile=None,
        )
        assert resp["image_url"] == "http://img/1"
        assert resp["svg_path"] == "M0,0"
        mock_client.generate.assert_called_once()
        mock_converter.convert_url_to_svg.assert_awaited_once_with(
            "http://img/1", skeletonize=True, reorder_strokes=True
        )
        mock_optimize.assert_called_once()
        assert mock_optimize.call_args.kwargs.get("close") is False

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    @patch("device_gateway.device_draw_handler.SVGConverter")
    @patch("device_gateway.device_draw_handler.validate_svg_path")
    @patch("device_gateway.device_draw_handler.optimize_svg_path")
    @patch("device_gateway.device_draw_handler.precheck_draw_motion_path")
    async def test_motion_bounds_precheck_failure(
        self,
        mock_precheck,
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
            return_value={
                "status": "success",
                "svg_path": "M0,0",
                "width": 100,
                "height": 200,
            }
        )
        mock_converter_cls.return_value = mock_converter

        mock_validate.return_value = SimpleNamespace(valid=True, errors=[])
        mock_optimize.return_value = SimpleNamespace(
            optimized_path="M0,0",
            original_points=10,
            optimized_points=5,
            reduction_ratio=0.5,
        )
        mock_precheck.return_value = "motion point 0 (150,50,0) outside workspace 100x100mm"

        resp = await handle_device_draw("a cat")
        assert resp["status"] == "partial"
        assert "Motion bounds precheck failed" in resp["error"]
        assert resp["svg_path"] is None

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt")
    @patch("device_gateway.image_fallback._generate_image_urls")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_image_generation_failure_records_retry_hint(
        self, mock_client_cls, mock_gen_urls, mock_enhance
    ):
        mock_enhance.side_effect = lambda prompt, **kwargs: prompt
        mock_client = MagicMock()
        mock_client.generate.return_value = {"status": "failed", "error": "rate limited"}
        mock_client_cls.return_value = mock_client
        # 降级链路也返回空，使整体回到 failed（本测试关注 retry hint 记录，非降级）
        mock_gen_urls.return_value = ([], "none", 0)

        resp = await handle_device_draw("a cat", device_id="dev-retry")
        assert resp["status"] == "failed"

        resp2 = await handle_device_draw("a cat", device_id="dev-retry")
        assert mock_enhance.call_count == 2
        assert mock_enhance.call_args_list[1].kwargs.get("previous_failed_prompts") == ["a cat"]


# NOTE: Additional TestHandleDeviceDraw tests moved to
# test_device_draw_handler_part2.py
# NOTE: DashScope 降级链路测试见 test_device_draw_handler_fallback.py
