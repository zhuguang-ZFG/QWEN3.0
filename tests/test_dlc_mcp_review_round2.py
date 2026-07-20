"""Regression tests for 2026-07-20 round-2 review fixes in dlc_mcp.

CORE-O1: duplicate idempotency status is an idempotent success, not -32603.
CORE-O5: tools/call runs on a thread pool so ping is answered while a slow
tool call is in flight.
CORE-Y1: malformed JSON lines get a -32700 reply instead of a silent drop.
"""

from __future__ import annotations

import io
import json
import threading
from unittest.mock import MagicMock

from dlc_mcp import server, stdio_loop


def _http_resp(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


# ── CORE-O1: duplicate status ────────────────────────────────────────────────


def test_duplicate_status_is_idempotent_success_not_internal_error():
    client = MagicMock()
    client.post.return_value = _http_resp({"status": "duplicate", "error": "idempotency key already used"})
    out = server._format_submission(client, 7, "/dlc/tasks/dispatch", {"type": "write_text"})
    assert "error" not in out
    assert out["result"]["isError"] is False
    assert "已提交" in out["result"]["content"][0]["text"]


def test_failed_status_still_returns_internal_error():
    client = MagicMock()
    client.post.return_value = _http_resp({"status": "failed", "error": "boom"})
    out = server._format_submission(client, 7, "/dlc/tasks/dispatch", {"type": "write_text"})
    assert out["error"]["code"] == -32603


# ── CORE-Y1: malformed JSON is answered, not silently dropped ────────────────


def _run_loop(monkeypatch, lines: list[str], handler) -> list[dict]:
    written: list[dict] = []
    monkeypatch.setattr(stdio_loop, "write_response", written.append)
    monkeypatch.setattr(stdio_loop.sys, "stdin", io.StringIO("".join(f"{line}\n" for line in lines)))
    stdio_loop.run_stdio_loop(client=None, handler=handler)
    return written


def test_malformed_json_replies_parse_error_with_recovered_id(monkeypatch, caplog):
    written = _run_loop(monkeypatch, ['{"jsonrpc": "2.0", "id": 5, "method": bad}'], handler=None)
    assert written == [{"jsonrpc": "2.0", "id": 5, "error": {"code": -32700, "message": "Parse error"}}]
    assert any("malformed JSON-RPC line" in rec.message for rec in caplog.records)


def test_malformed_json_without_id_replies_null_id(monkeypatch):
    written = _run_loop(monkeypatch, ["not json at all"], handler=None)
    assert written[0]["id"] is None
    assert written[0]["error"]["code"] == -32700


# ── CORE-O5: ping answered while a slow tools/call is in flight ──────────────


def test_ping_answered_while_tools_call_blocks(monkeypatch):
    order: list[str] = []
    release = threading.Event()

    def handler(_client, req):
        if req.get("method") == "tools/call":
            assert release.wait(timeout=5), "ping never released the slow tool call"
            order.append("tool")
            return {"jsonrpc": "2.0", "id": req["id"], "result": {"content": [], "isError": False}}
        order.append("ping")
        release.set()
        return {"jsonrpc": "2.0", "id": req["id"], "result": {}}

    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "dlc.write_text"}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
    ]
    written = _run_loop(monkeypatch, lines, handler)
    # The ping is answered by the main thread while the tool call is blocked.
    assert order == ["ping", "tool"]
    assert {resp["id"] for resp in written} == {1, 2}
