"""DashScope 图生真实 API 夹具（准入 / 发布证据用，默认跳过）。

启用条件（同时满足）：
  - ``ALIYUN_API_KEY`` 已设置
  - ``LIMA_DEVICE_ADMISSION_LIVE=1``

运行：
  set LIMA_DEVICE_ADMISSION_LIVE=1
  pytest tests/test_dashscope_image_live.py -v

或：
  python scripts/eval_device_model_role.py --role image_generator --live
"""

from __future__ import annotations

import os

import pytest

from dashscope_image_client import DashScopeImageClient

pytestmark = pytest.mark.dashscope_live


def _live_admission_enabled() -> bool:
    key = os.environ.get("ALIYUN_API_KEY", "").strip()
    flag = os.environ.get("LIMA_DEVICE_ADMISSION_LIVE", "").strip().lower()
    return bool(key) and flag in {"1", "true", "yes", "on"}


def _skip_reason() -> str:
    if not os.environ.get("ALIYUN_API_KEY", "").strip():
        return "ALIYUN_API_KEY 未设置"
    return "设置 LIMA_DEVICE_ADMISSION_LIVE=1 以启用真实图生夹具"


@pytest.fixture
def live_client() -> DashScopeImageClient:
    if not _live_admission_enabled():
        pytest.skip(_skip_reason())
    return DashScopeImageClient()


def test_live_wanx_sync_generate_returns_url(live_client: DashScopeImageClient):
    """Image Generator 准入：Wanx 同步图生返回可访问 URL。"""
    result = live_client.generate(
        prompt="minimal flat red circle icon, white background",
        model="wanx-v1",
        size="512*512",
        n=1,
    )
    assert result["status"] == "success", result.get("error")
    assert result["images"], "expected at least one image"
    url = result["images"][0]["url"]
    assert isinstance(url, str) and url.startswith("http"), url


def test_live_wanx_async_submit_and_fetch(live_client: DashScopeImageClient):
    """Image Generator 准入：异步提交 + 轮询可完成。"""
    import asyncio
    import time

    pending = asyncio.run(
        live_client.generate_async(
            prompt="minimal blue square icon, white background",
            model="wanx-v1",
            size="512*512",
        )
    )
    assert pending["status"] == "pending", pending.get("error")
    task_id = pending["task_id"]
    assert task_id

    deadline = time.time() + 120
    last = pending
    while time.time() < deadline:
        last = live_client.get_task_result(task_id)
        if last["status"] == "success":
            break
        if last["status"] == "failed":
            pytest.fail(last.get("error") or "async task failed")
        time.sleep(3)

    assert last["status"] == "success", last.get("error")
    assert last["images"] and last["images"][0]["url"].startswith("http")
