"""Verify RequestIDMiddleware propagates/generates X-Request-ID.

切片 A：每条响应必须带 ``X-Request-ID``；自带则透传，缺失则生成；并发不串。
用最小 FastAPI app 隔离中间件行为，避免触发 ``server_dlc`` 的全量路由装配。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from dlc_api.middleware import add_request_id_middleware


def _make_app() -> FastAPI:
    app = FastAPI()
    add_request_id_middleware(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/echo")
    def echo(request: Request) -> dict[str, str]:
        return {"rid": request.state.request_id}

    return app


def test_generates_request_id_when_absent() -> None:
    client = TestClient(_make_app())
    resp = client.get("/health")
    rid = resp.headers.get("x-request-id")
    assert rid, "expected X-Request-ID to be generated"
    assert len(rid) >= 8


def test_propagates_incoming_request_id() -> None:
    client = TestClient(_make_app())
    resp = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers.get("x-request-id") == "abc123"


def test_request_state_carries_id() -> None:
    client = TestClient(_make_app())
    resp = client.get("/echo", headers={"X-Request-ID": "state-7"})
    assert resp.json()["rid"] == "state-7"


def test_concurrent_requests_get_distinct_ids() -> None:
    client = TestClient(_make_app())
    ids = {client.get("/health").headers.get("x-request-id") for _ in range(5)}
    assert len(ids) == 5, f"expected distinct generated ids, got {ids}"


def test_sanitizes_malicious_request_id() -> None:
    """超长/含换行/空格的 X-Request-ID 被清洗：长度 ≤128，无 \\n/\\r/空格。"""
    client = TestClient(_make_app())
    rid_payload = "a" * 300 + "\n injected\r line " + "b" * 300
    resp = client.get("/health", headers={"X-Request-ID": rid_payload})
    sanitized = resp.headers.get("x-request-id")
    assert sanitized is not None
    assert len(sanitized) <= 128
    assert "\n" not in sanitized
    assert "\r" not in sanitized
    assert " " not in sanitized
