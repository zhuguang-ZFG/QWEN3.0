"""Concurrency tests for http_caller async/sync paths (CQ-022/023 follow-up)."""

import asyncio
import json
import threading
from unittest.mock import MagicMock, patch


import http_caller


class _CountingAsyncClient:
    def __init__(self, label: str, json_data: dict, delay: float = 0.0):
        self.label = label
        self.json_data = json_data
        self.delay = delay
        self.post_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        self.post_calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        response = MagicMock()
        response.json.return_value = self.json_data
        response.raise_for_status.return_value = None
        return response


class _AsyncStreamClient:
    def __init__(self, lines: list[str], delay: float = 0.0):
        self.lines = lines
        self.delay = delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        parent = self

        class _Ctx:
            async def __aenter__(self_inner):
                return parent

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        for line in self.lines:
            yield line


async def _collect_async(async_iterable):
    return [chunk async for chunk in async_iterable]


BACKEND_CFG = {
    "url": "https://test.com/v1/chat/completions",
    "key": "sk-test",
    "model": "test-model",
    "fmt": "openai",
    "timeout": 10,
}


@patch("http_caller.health_tracker")
@patch("http_caller._build_async_client")
def test_call_api_async_parallel_success(mock_build_async_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    clients = [
        _CountingAsyncClient(f"c{i}", {"choices": [{"message": {"content": f"ok{i}"}}]}, delay=0.01) for i in range(8)
    ]
    mock_build_async_client.side_effect = clients

    async def _run():
        tasks = [
            http_caller.call_api_async(
                "async_backend",
                [{"role": "user", "content": f"hi {i}"}],
            )
            for i in range(8)
        ]
        return await asyncio.gather(*tasks)

    with patch.dict(http_caller.BACKENDS, {"async_backend": dict(BACKEND_CFG)}):
        results = asyncio.run(_run())

    assert results == [f"ok{i}" for i in range(8)]
    assert all(client.post_calls == 1 for client in clients)
    assert mock_ht.record_success.call_count == 8


@patch("http_caller.health_tracker")
@patch("http_caller._build_async_client")
def test_call_api_async_parallel_mixed_failures_isolated(mock_build_async_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False

    def _client_factory(backend, timeout):
        if backend.endswith("_fail"):
            raise RuntimeError("boom")
        return _CountingAsyncClient(
            backend,
            {"choices": [{"message": {"content": "fine"}}]},
        )

    mock_build_async_client.side_effect = _client_factory

    async def _run():
        async def _one(name: str):
            return await http_caller.call_api_async(
                name,
                [{"role": "user", "content": "hi"}],
            )

        tasks = [
            asyncio.create_task(_one("async_backend")),
            asyncio.create_task(_one("async_backend_fail")),
            asyncio.create_task(_one("async_backend")),
        ]
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                results.append(("ok", await task))
            except http_caller.BackendError as exc:
                results.append(("err", str(exc)))
        return results

    with patch.dict(
        http_caller.BACKENDS,
        {
            "async_backend": dict(BACKEND_CFG),
            "async_backend_fail": dict(BACKEND_CFG),
        },
    ):
        outcomes = asyncio.run(_run())

    assert sum(1 for kind, _ in outcomes if kind == "ok") == 2
    assert sum(1 for kind, _ in outcomes if kind == "err") == 1


@patch("http_caller.health_tracker")
@patch("http_caller._build_async_client")
def test_call_api_stream_async_parallel_collects_chunks(mock_build_async_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    line = "data: " + json.dumps({"choices": [{"delta": {"content": "x"}}]})
    clients = [_AsyncStreamClient([line, "data: [DONE]"], delay=0.01) for _ in range(5)]
    mock_build_async_client.side_effect = clients

    async def _run():
        tasks = [
            _collect_async(
                http_caller.call_api_stream_async(
                    "async_stream",
                    [{"role": "user", "content": f"hi {i}"}],
                )
            )
            for i in range(5)
        ]
        return await asyncio.gather(*tasks)

    with patch.dict(http_caller.BACKENDS, {"async_stream": dict(BACKEND_CFG)}):
        results = asyncio.run(_run())

    assert results == [["x"]] * 5


def _setup_burst_mocks(mock_build_client, mock_ht, mock_get_key, mock_ensure_env_pool, mock_is_exhausted) -> tuple:
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = "sk-pooled"

    mock_client = MagicMock()
    mock_resp = MagicMock()
    _resp_json = {"choices": [{"message": {"content": "ok"}}]}
    mock_resp.json.return_value = _resp_json
    mock_resp.text = json.dumps(_resp_json)
    mock_resp.raise_for_status.return_value = None
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp
    mock_build_client.return_value = mock_client

    cfg = dict(BACKEND_CFG)
    cfg["key_pool"] = "burst-provider"
    return cfg


def _run_burst_workers(cfg: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    results: list[str] = []
    lock = threading.Lock()

    def _worker():
        try:
            with patch.dict(http_caller.BACKENDS, {"burst_backend": cfg}):
                result = http_caller.call_api(
                    "burst_backend",
                    [{"role": "user", "content": "hi"}],
                )
            with lock:
                results.append(result)
        except Exception as exc:
            with lock:
                errors.append(str(exc))

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return errors, results


@patch("http_caller.key_pool.is_exhausted")
@patch("http_caller.key_pool.ensure_env_pool")
@patch("http_caller.key_pool.get_key")
@patch("http_caller.health_tracker")
@patch("http_caller._build_client")
def test_call_api_thread_burst_all_succeed(
    mock_build_client,
    mock_ht,
    mock_get_key,
    mock_ensure_env_pool,
    mock_is_exhausted,
):
    cfg = _setup_burst_mocks(mock_build_client, mock_ht, mock_get_key, mock_ensure_env_pool, mock_is_exhausted)
    errors, results = _run_burst_workers(cfg)

    assert not errors
    assert len(results) == 4
    assert all("ok" in result for result in results)
    assert mock_ht.record_success.call_count == 4
