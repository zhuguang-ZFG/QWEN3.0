"""Tests for device gateway dispatch helpers."""

from __future__ import annotations

import pytest
from starlette.datastructures import Headers, QueryParams

from routes.device_gateway_dispatch import extract_ws_token


class _FakeWebSocket:
    def __init__(self, headers: dict[str, str] | None = None, query: dict[str, str] | None = None) -> None:
        self.headers = Headers(headers or {})
        self.query_params = QueryParams(query or {})


@pytest.mark.parametrize(
    ("headers", "query", "expected"),
    [
        ({"authorization": "Bearer secret-token"}, {}, "secret-token"),
        ({"authorization": "secret-token"}, {}, "secret-token"),
        ({}, {"token": "query-token"}, "query-token"),
        ({}, {"token": "Bearer query-token"}, "query-token"),
        ({}, {"authorization": "Bearer auth-query-token"}, "auth-query-token"),
        ({}, {"authorization": "auth-query-token"}, "auth-query-token"),
        ({}, {"token": "token-wins", "authorization": "auth-loses"}, "token-wins"),
        ({}, {}, ""),
    ],
)
def test_extract_ws_token(headers: dict[str, str], query: dict[str, str], expected: str) -> None:
    ws = _FakeWebSocket(headers=headers, query=query)
    assert extract_ws_token(ws) == expected
