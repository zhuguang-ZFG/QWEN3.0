"""Concurrency tests for TOCTOU fixes: activation, captcha, dispatch."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from device_logic.activation import check_activation_code, new_activation_code, reset_activation_store_for_tests
from device_logic.captcha import create_captcha, verify_captcha
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests


# ---------------------------------------------------------------------------
# Fix 1: activation code -- atomic DELETE, no TOCTOU
# ---------------------------------------------------------------------------


def setup_function() -> None:
    reset_activation_store_for_tests()


def _consume(code: str) -> bool:
    return check_activation_code(code)


def test_activation_concurrent_consume_gives_exactly_one_winner() -> None:
    """两个线程消费同一有效激活码，恰好一个返回 True."""
    code = new_activation_code()
    assert check_activation_code(code) is True  # first consume works

    # Re-insert for the real concurrent test
    reset_activation_store_for_tests()
    code = new_activation_code()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_consume, [code, code]))

    assert results.count(True) == 1, f"expected exactly 1 True, got {results}"
    assert results.count(False) == 1, f"expected exactly 1 False, got {results}"


def test_activation_expired_code_returns_false() -> None:
    """过期码消费返回 False."""
    with patch("device_logic.activation.time.time") as mock_time:
        mock_time.return_value = 1000.0
        code = new_activation_code()
        mock_time.return_value = 2000.0  # past TTL
        assert check_activation_code(code) is False


# ---------------------------------------------------------------------------
# Fix 2: captcha -- consumed on first attempt regardless of success/failure
# ---------------------------------------------------------------------------


def test_captcha_wrong_answer_consumes_the_row() -> None:
    """同一 captcha_id 验证失败一次后，第二次返回不存在/过期."""
    captcha_id, _ = create_captcha("ABCD")
    first = verify_captcha(captcha_id, "wrong")
    assert first is not None, "wrong answer should return error"

    second = verify_captcha(captcha_id, "ABCD")
    assert second is not None, "second attempt should also return error (consumed on first)"


def test_captcha_correct_answer_consumes_the_row() -> None:
    """验证成功后，同一 captcha_id 不再可用."""
    captcha_id, code = create_captcha()
    first = verify_captcha(captcha_id, code)
    assert first is None, "correct answer should succeed"

    second = verify_captcha(captcha_id, code)
    assert second is not None, "already consumed, should fail"


# ---------------------------------------------------------------------------
# Fix 3: dispatch -- per-device lock serialises busy check + creation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_tasks() -> None:
    install_task_store_for_tests()
    reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_dispatch_concurrent_to_same_device_one_rejected() -> None:
    """两个并发 dispatch_task 到同一空闲设备，一个 sent/queued 一个 rejected(device_busy)."""
    from dlc_core.dispatch import dispatch_task

    device_id = "dev-concur-1"
    task_payload = {"text": "write hello", "request_id": "req-1", "source": "test", "entrypoint": ""}

    async def dispatch_once() -> dict:
        return await dispatch_task(device_id, task_payload)

    results = await asyncio.gather(dispatch_once(), dispatch_once())

    statuses = [r["status"] for r in results]
    errors = [r.get("error") for r in results]

    assert statuses.count("rejected") == 1, f"expected 1 rejected, got {statuses}"
    assert errors.count("device_busy") == 1, f"expected 1 device_busy, got {errors}"

    # The non-rejected one should have a status that indicates acceptance
    accepted = [s for s in statuses if s != "rejected"]
    assert len(accepted) == 1
    assert accepted[0] in ("queued", "sent", "queued_no_delivery"), f"unexpected accepted status: {accepted}"


@pytest.mark.asyncio
async def test_dispatch_different_devices_both_accepted() -> None:
    """不同设备的并发 dispatch 互相不阻塞."""
    from dlc_core.dispatch import dispatch_task

    task_payload = {"text": "write hello", "request_id": "req-2", "source": "test", "entrypoint": ""}

    async def dispatch_for(device_id: str) -> dict:
        return await dispatch_task(device_id, task_payload)

    results = await asyncio.gather(dispatch_for("dev-a"), dispatch_for("dev-b"))

    for r in results:
        assert r["status"] != "rejected", f"unexpected rejection: {r}"
