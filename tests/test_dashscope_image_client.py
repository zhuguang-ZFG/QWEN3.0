"""测试 DashScope 图生 API 客户端"""

import pytest
from unittest.mock import Mock, patch
from dashscope_image_client import DashScopeImageClient


@pytest.fixture
def mock_response_success():
    """模拟成功响应"""
    mock = Mock()
    mock.status_code = 200
    mock.output = {
        "task_id": "task-123",
        "results": [{"url": "https://example.com/image1.jpg"}, {"url": "https://example.com/image2.jpg"}],
    }
    return mock


@pytest.fixture
def mock_response_failed():
    """模拟失败响应"""
    mock = Mock()
    mock.status_code = 400
    mock.code = "InvalidParameter"
    mock.message = "Invalid prompt"
    return mock


def test_generate_success(mock_response_success):
    """测试同步生成成功"""
    with patch("dashscope_image_client.ImageSynthesis.call", return_value=mock_response_success):
        client = DashScopeImageClient(api_key="test-key")
        result = client.generate(prompt="a cat", model="wanx-v1")

        assert result["status"] == "success"
        assert len(result["images"]) == 2
        assert result["images"][0]["url"] == "https://example.com/image1.jpg"
        assert result["task_id"] == "task-123"
        assert result["error"] is None


def test_generate_failed(mock_response_failed):
    """测试同步生成失败"""
    with patch("dashscope_image_client.ImageSynthesis.call", return_value=mock_response_failed):
        client = DashScopeImageClient(api_key="test-key")
        result = client.generate(prompt="a cat")

        assert result["status"] == "failed"
        assert len(result["images"]) == 0
        assert "InvalidParameter" in result["error"]


def test_generate_exception():
    """测试异常处理"""
    with patch("dashscope_image_client.ImageSynthesis.call", side_effect=Exception("Network error")):
        client = DashScopeImageClient(api_key="test-key")
        result = client.generate(prompt="a cat")

        assert result["status"] == "failed"
        assert "Network error" in result["error"]


def test_async_generate_success(mock_response_success):
    """测试异步生成成功"""
    with patch("dashscope_image_client.ImageSynthesis.async_call", return_value=mock_response_success):
        client = DashScopeImageClient(api_key="test-key")
        import asyncio

        result = asyncio.run(client.generate_async(prompt="a cat"))

        assert result["status"] == "pending"
        assert result["task_id"] == "task-123"
        assert result["error"] is None


def test_get_task_result_success(mock_response_success):
    """测试查询任务成功"""
    mock_response_success.output["task_status"] = "SUCCEEDED"
    with patch("dashscope_image_client.ImageSynthesis.fetch", return_value=mock_response_success):
        client = DashScopeImageClient(api_key="test-key")
        result = client.get_task_result(task_id="task-123")

        assert result["status"] == "success"
        assert len(result["images"]) == 2


def test_get_task_result_pending(mock_response_success):
    """测试查询任务进行中"""
    mock_response_success.output["task_status"] = "RUNNING"
    with patch("dashscope_image_client.ImageSynthesis.fetch", return_value=mock_response_success):
        client = DashScopeImageClient(api_key="test-key")
        result = client.get_task_result(task_id="task-123")

        assert result["status"] == "pending"
        assert len(result["images"]) == 0
