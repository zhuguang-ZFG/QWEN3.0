"""SSE line parser used by sync and async chat completion streams."""

from __future__ import annotations

from typing import Any, Iterator


def _iter_sse_lines(response: Any) -> Iterator[str]:
    """Yield stripped SSE data lines from an httpx response.

    Works for both httpx.Response (sync) and httpx.AsyncResponseStream (async)
    because both expose ``iter_lines()``.
    """
    for line in response.iter_lines():
        if line.startswith("data: "):
            yield line[6:]


def iter_sse_chunks(response: Any) -> Iterator[dict[str, Any]]:
    """Yield parsed SSE JSON chunks, skipping ``[DONE]``."""
    import json

    for line in _iter_sse_lines(response):
        if line == "[DONE]":
            continue
        if not line:
            continue
        yield json.loads(line)
