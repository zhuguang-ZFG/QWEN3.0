"""Tests for image generation tools (lima_fc_tools/image_tools.py).

Covers: API key missing, sync success, async poll success, HTTP error,
network exception, task failure, polling timeout.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lima_fc_tools.image_tools import _generate_image

# -- Helpers ---------------------------------------------------------------

def _mock_async_client(**kw):
    """Create a mock httpx.AsyncClient with __aenter__ → self."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    if "post_resp" in kw:
        client.post.return_value = kw["post_resp"]
    if "get_resp" in kw:
        client.get.return_value = kw["get_resp"]
    return client


def _resp(status: int, json_body: dict) -> MagicMock:
    """Create a mock httpx.Response with given status and JSON body."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body
    return r


# -- API key missing -------------------------------------------------------

@pytest.mark.asyncio
async def test_api_key_missing():
    """When LIMA_IMAGE_GEN_API_KEY is empty, return error immediately."""
    with patch.dict(os.environ, {}, clear=True):
        result = await _generate_image("a beautiful sunset")
    assert "error" in result
    assert "LIMA_IMAGE_GEN_API_KEY" in result["error"]


# -- Success: sync response (results directly, no task_id) -----------------

@pytest.mark.asyncio
async def test_success_sync_response():
    """When API returns results directly, return image_url."""
    resp = _resp(200, {"output": {"results": [{"url": "https://img.example/1.png"}]}})
    client = _mock_async_client(post_resp=resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=client):
            result = await _generate_image("a cat", style="anime")

    assert result["prompt"] == "a cat"
    assert result["style"] == "anime"
    assert result["image_url"] == "https://img.example/1.png"


# -- Success: async polled (task_id → SUCCEEDED) ---------------------------

@pytest.mark.asyncio
async def test_success_polled():
    """When API returns task_id, poll until SUCCEEDED."""
    post_resp = _resp(200, {"output": {"task_id": "task-123"}})
    poll_resp = _resp(200, {
        "output": {
            "task_status": "SUCCEEDED",
            "results": [{"url": "https://img.example/polled.png"}],
        }
    })

    init = _mock_async_client(post_resp=post_resp)
    poll = _mock_async_client(get_resp=poll_resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", side_effect=[init] + [poll] * 30):
            with patch("asyncio.sleep", AsyncMock()):
                result = await _generate_image("a dog", size="720*1280")

    assert result["image_url"] == "https://img.example/polled.png"
    assert result["task_id"] == "task-123"
    assert result["size"] == "720*1280"


# -- No task_id and no results ---------------------------------------------

@pytest.mark.asyncio
async def test_no_task_id_or_results():
    """When response has neither task_id nor results, return error."""
    resp = _resp(200, {"output": {}})
    client = _mock_async_client(post_resp=resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=client):
            result = await _generate_image("test")

    assert "error" in result
    assert "No task_id" in result["error"]


# -- HTTP error ------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_http_error():
    """When API returns non-200, return error with status code."""
    resp = _resp(401, {"error": "unauthorized"})
    client = _mock_async_client(post_resp=resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=client):
            result = await _generate_image("test")

    assert "error" in result
    assert "401" in result["error"]


# -- Network exception -----------------------------------------------------

@pytest.mark.asyncio
async def test_network_exception():
    """When network fails, return error with exception message."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.side_effect = OSError("Connection refused")

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=client):
            result = await _generate_image("test")

    assert "error" in result
    assert "Connection refused" in result["error"]


# -- Task failure ----------------------------------------------------------

@pytest.mark.asyncio
async def test_task_failed():
    """When async task reports FAILED, return error with reason."""
    post_resp = _resp(200, {"output": {"task_id": "task-fail"}})
    fail_resp = _resp(200, {
        "output": {
            "task_status": "FAILED",
            "message": "content policy violation",
        }
    })

    init = _mock_async_client(post_resp=post_resp)
    poll = _mock_async_client(get_resp=fail_resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", side_effect=[init] + [poll] * 30):
            with patch("asyncio.sleep", AsyncMock()):
                result = await _generate_image("bad content")

    assert "error" in result
    assert "content policy violation" in result["error"]
    assert result["task_id"] == "task-fail"


# -- Polling timeout -------------------------------------------------------

@pytest.mark.asyncio
async def test_polling_timeout():
    """After 30 polls with RUNNING status, return timeout error."""
    post_resp = _resp(200, {"output": {"task_id": "task-timeout"}})
    running_resp = _resp(200, {"output": {"task_status": "RUNNING"}})

    init = _mock_async_client(post_resp=post_resp)
    poll = _mock_async_client(get_resp=running_resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", side_effect=[init] + [poll] * 30):
            with patch("asyncio.sleep", AsyncMock()):
                result = await _generate_image("timeout test")

    assert "error" in result
    assert "timed out" in result["error"]
    assert result["task_id"] == "task-timeout"


# -- Task succeeded but no results -----------------------------------------

@pytest.mark.asyncio
async def test_task_succeeded_no_results():
    """When SUCCEEDED but results list is empty, return error."""
    post_resp = _resp(200, {"output": {"task_id": "task-empty"}})
    empty_resp = _resp(200, {
        "output": {"task_status": "SUCCEEDED", "results": []}
    })

    init = _mock_async_client(post_resp=post_resp)
    poll = _mock_async_client(get_resp=empty_resp)

    with patch.dict(os.environ, {"LIMA_IMAGE_GEN_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", side_effect=[init] + [poll] * 30):
            with patch("asyncio.sleep", AsyncMock()):
                result = await _generate_image("test")

    assert "error" in result
    assert "no results" in result["error"]
