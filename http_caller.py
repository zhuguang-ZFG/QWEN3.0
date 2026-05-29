"""
LiMa HTTP Caller — unified backend transport layer (thin re-export).

Modules:
  http_errors.py           BackendError + status helpers
  http_request_builder.py  client factory, headers, body, key pool
  http_response.py         answer/usage/SSE parsing
  http_stream.py           sync/async SSE streaming
  http_sync.py             sync call_api / call_raw / probe
  http_async.py            async call_api / call_raw
"""

from __future__ import annotations

import health_tracker
import key_pool
from response_cleaner import clean_response, _is_backend_error

from backends import BACKENDS, GFW_BACKENDS
from http_async import call_api_async, call_raw_async
from http_errors import BackendError, _emit_backend_error, _extract_code, _extract_retry_after
from http_request_builder import (
    GFW_PROXY_URL,
    GFW_USER_AGENT,
    _build_async_client,
    _build_body,
    _build_client,
    _build_headers,
    _has_key,
    _key_pool_provider,
    _report_key_result,
    _select_key,
)
from http_response import _extract_answer, _extract_usage, _parse_sse_chunk
from http_stream import call_api_stream, call_api_stream_async
from http_sync import call_api, call_raw, probe

DEBUG = __import__("os").environ.get("LIMA_DEBUG", "") == "1"
