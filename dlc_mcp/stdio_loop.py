"""Stdio JSON-RPC read loop for the DLC MCP server.

CORE-O5: tools/call can block on dlc_api for 25s+ (draw_from_image), which is
longer than the broker's ~24s ping window. Compressing the httpx timeout below
that window would break slow-but-legitimate tools, so tools/call requests run
on a small thread pool while the main thread keeps reading stdin and answers
ping (and the other fast methods) inline. httpx.Client is thread-safe; stdout
writes are serialized with a lock so response lines never interleave.

CORE-Y1: malformed JSON lines are logged and answered with a best-effort
JSON-RPC -32700 Parse error instead of being silently dropped.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

_TOOL_CALL_WORKERS = 4
_stdout_lock = threading.Lock()

# Best-effort id recovery from a malformed line (string or integer id).
_ID_RE = re.compile(r'"id"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+)')


def write_response(resp: dict) -> None:
    """Write one JSON-RPC response line to stdout (thread-safe)."""
    if not resp or (resp.get("id") is None and resp.get("error") is None):
        return
    payload = json.dumps(resp, ensure_ascii=False) + "\n"
    with _stdout_lock:
        sys.stdout.buffer.write(payload.encode("utf-8"))
        sys.stdout.buffer.flush()


def _extract_request_id(line: str) -> Any:
    match = _ID_RE.search(line)
    if match is None:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def _reply_parse_error(line: str, exc: Exception) -> None:
    """CORE-Y1: log the malformed line and reply -32700 (id recovered best-effort)."""
    logger.warning("malformed JSON-RPC line (%s): %.120r", exc, line)
    write_response(
        {
            "jsonrpc": "2.0",
            "id": _extract_request_id(line),
            "error": {"code": -32700, "message": "Parse error"},
        }
    )


def _run_request(client: Any, handler: Callable[[Any, Any], dict], req: Any) -> None:
    """Run one request through the handler; exceptions become -32603, never crash."""
    try:
        resp = handler(client, req)
    except Exception as exc:  # noqa: BLE001 - worker/main loop must not die
        logger.warning("MCP handle_request internal error: %s", exc)
        req_id = req.get("id") if isinstance(req, dict) else None
        resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": "Internal error"}}
    write_response(resp)


def run_stdio_loop(client: Any, handler: Callable[[Any, Any], dict]) -> None:
    """Read JSON-RPC lines from stdin until EOF; run slow tools/call on a pool."""
    with ThreadPoolExecutor(max_workers=_TOOL_CALL_WORKERS, thread_name_prefix="mcp-tool") as pool:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                _reply_parse_error(line, exc)
                continue
            if isinstance(req, dict) and req.get("method") == "tools/call":
                pool.submit(_run_request, client, handler, req)
            else:
                _run_request(client, handler, req)
