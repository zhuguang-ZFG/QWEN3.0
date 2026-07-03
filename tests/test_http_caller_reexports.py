"""Verify http_caller re-exports the expected public and internal symbols.

This is a characterization test: it locks the facade contract of
http_caller.py so that future refactors do not accidentally drop symbols
that downstream modules import directly from the facade.
"""

from __future__ import annotations

import pytest

import http_caller


@pytest.mark.parametrize(
    "symbol",
    [
        # From response_cleaner
        "clean_response",
        "_is_backend_error",
        # From backend registries
        "GFW_BACKENDS",
        "BACKENDS",
        # From http_async
        "call_api_async",
        "call_raw_async",
        # From http_errors
        "BackendError",
        "_emit_backend_error",
        "_extract_code",
        "_extract_retry_after",
        # From http_request_builder
        "GFW_PROXY_URL",
        "GFW_USER_AGENT",
        "_build_async_client",
        "_build_body",
        "_build_client",
        "_build_headers",
        "_has_key",
        "_key_pool_provider",
        "_report_key_result",
        "_select_key",
        # From http_response
        "_extract_answer",
        "_extract_usage",
        "_parse_sse_chunk",
        # From http_stream
        "call_api_stream",
        "call_api_stream_async",
        # From http_sync
        "call_api",
        "call_raw",
        "probe",
        # Module-level flag
        "DEBUG",
    ],
)
def test_http_caller_exports_symbol(symbol: str) -> None:
    assert hasattr(http_caller, symbol), f"http_caller is missing {symbol}"


def test_http_caller_callable_exports_are_callable() -> None:
    for name in (
        "call_api",
        "call_raw",
        "probe",
        "call_api_async",
        "call_raw_async",
        "call_api_stream",
        "call_api_stream_async",
        "clean_response",
        "BackendError",
    ):
        obj = getattr(http_caller, name)
        assert callable(obj), f"{name} should be callable"
