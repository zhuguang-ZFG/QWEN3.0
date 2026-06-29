"""DashScope 生图降级链路测试（device_draw_handler → image_fallback）。

从 test_device_draw_handler.py 拆出（保持单文件 ≤300 行约束）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from device_gateway.device_draw_handler import _generate_image
from session_memory.store import _get_conn, set_db_path


@pytest.fixture(autouse=True)
def _reset_db(tmp_path):
    """每个测试用独立 DB，避免 device_draw 历史污染。"""
    set_db_path(str(tmp_path / "device_draw_fallback.db"))
    conn = _get_conn()
    conn.execute("DELETE FROM memories")
    conn.commit()
    conn.close()
    yield


class TestImageFallback:
    """DashScope 失败时降级到 /v1/images 多后端链路的测试。"""

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
    @patch("device_gateway.image_fallback._generate_image_urls")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_dashscope_failure_triggers_image_fallback(self, mock_client_cls, mock_gen_urls):
        """DashScope 失败 → 降级链路成功，应返回降级结果。"""
        mock_client = MagicMock()
        mock_client.generate.return_value = {"status": "failed", "images": [], "error": "rate limited"}
        mock_client_cls.return_value = mock_client
        mock_gen_urls.return_value = (
            [{"url": "http://fallback/img.png"}],
            "agnes",
            100,
        )

        result = await _generate_image("a cat", "wanx2.1-t2i-turbo", "1024*1024", device_id="dev-fb")
        assert result["status"] == "success"
        assert result["images"][0]["url"] == "http://fallback/img.png"
        # 确认 size 格式从 '*' 转成 'x' 传给降级链路
        assert mock_gen_urls.call_args.args[1] == "1024x1024"

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
    @patch("device_gateway.image_fallback._generate_image_urls")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_both_dashscope_and_fallback_fail_returns_dashscope_error(self, mock_client_cls, mock_gen_urls):
        """DashScope + 降级都失败，应返回 DashScope 原始错误（保留诊断信息）。"""
        mock_client = MagicMock()
        mock_client.generate.return_value = {"status": "failed", "images": [], "error": "dashscope down"}
        mock_client_cls.return_value = mock_client
        mock_gen_urls.return_value = ([], "none", 0)

        result = await _generate_image("a cat", "wanx2.1-t2i-turbo", "1024*1024", device_id="dev-fb")
        assert result["status"] == "failed"
        assert result["error"] == "dashscope down"

    @patch("device_gateway.device_draw_handler.enhance_drawing_prompt", lambda p, **kwargs: p)
    @patch("device_gateway.image_fallback._generate_image_urls")
    @patch("device_gateway.device_draw_handler.DashScopeImageClient")
    async def test_dashscope_success_skips_fallback(self, mock_client_cls, mock_gen_urls):
        """DashScope 成功时不触发降级（零开销）。"""
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "status": "success",
            "images": [{"url": "http://dashscope/img.png"}],
            "error": None,
        }
        mock_client_cls.return_value = mock_client

        result = await _generate_image("a cat", "wanx2.1-t2i-turbo", "1024*1024", device_id="dev-ok")
        assert result["images"][0]["url"] == "http://dashscope/img.png"
        # 降级链路不应被调用
        mock_gen_urls.assert_not_called()
