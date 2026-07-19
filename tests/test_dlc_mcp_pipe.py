"""Tests for dlc_mcp.mcp_pipe helpers."""

from __future__ import annotations

import asyncio

import pytest

import dlc_mcp.mcp_pipe as mcp_pipe
from dlc_mcp.mcp_pipe import _default_server_cmd, _websocket_header_kwargs, run_bridge


def test_websocket_header_kwargs_supports_new_api() -> None:
    def connect(uri: str, *, additional_headers=None):
        return uri, additional_headers

    assert _websocket_header_kwargs(connect, {"Authorization": "Bearer x"}) == {
        "additional_headers": {"Authorization": "Bearer x"}
    }


def test_websocket_header_kwargs_supports_old_api() -> None:
    def connect(uri: str, *, extra_headers=None):
        return uri, extra_headers

    assert _websocket_header_kwargs(connect, {"Authorization": "Bearer x"}) == {
        "extra_headers": {"Authorization": "Bearer x"}
    }


def test_default_server_cmd_points_to_local_server() -> None:
    cmd = _default_server_cmd()
    assert cmd[0]
    assert cmd[1].endswith(("dlc_mcp/server.py", "dlc_mcp\\server.py"))


def test_run_bridge_rejects_empty_endpoint() -> None:
    """No endpoint → early exit code 2, no session spawned."""
    rc = asyncio.run(run_bridge("", ["python", "server.py"], "ua"))
    assert rc == 2


def test_run_bridge_reconnects_with_exponential_backoff(monkeypatch) -> None:
    """A session that keeps failing must reconnect with exponential backoff.

    XiaoZhi drops idle MCP connections; the bridge must reconnect instead of
    crashing. We let _run_session always raise, capture the sleep delays, and
    break the otherwise-infinite loop by cancelling after several retries.
    """
    delays: list[float] = []

    async def _always_fail(endpoint, server_cmd, user_agent):
        raise ConnectionError("simulated WS drop")

    async def _fake_sleep(delay):
        delays.append(delay)
        if len(delays) >= 5:
            raise asyncio.CancelledError

    monkeypatch.setattr(mcp_pipe, "_run_session", _always_fail)
    monkeypatch.setattr(mcp_pipe.asyncio, "sleep", _fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_bridge("wss://x", ["python", "server.py"], "ua"))

    # Exponential backoff, capped at _RECONNECT_MAX_DELAY.
    assert delays[0] == mcp_pipe._RECONNECT_MIN_DELAY
    assert delays[1] == mcp_pipe._RECONNECT_MIN_DELAY * 2
    assert delays[2] == mcp_pipe._RECONNECT_MIN_DELAY * 4
    assert all(d <= mcp_pipe._RECONNECT_MAX_DELAY for d in delays)


def test_run_bridge_resets_backoff_after_clean_session(monkeypatch) -> None:
    """A clean session end resets the backoff to the minimum delay."""
    delays: list[float] = []
    calls = {"n": 0}

    async def _clean_then_stop(endpoint, server_cmd, user_agent):
        calls["n"] += 1
        return None  # clean session end (WS closed by peer)

    async def _fake_sleep(delay):
        delays.append(delay)
        if len(delays) >= 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(mcp_pipe, "_run_session", _clean_then_stop)
    monkeypatch.setattr(mcp_pipe.asyncio, "sleep", _fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_bridge("wss://x", ["python", "server.py"], "ua"))

    # Every clean end sleeps the minimum delay, never escalating.
    assert delays == [mcp_pipe._RECONNECT_MIN_DELAY] * 3
    assert calls["n"] >= 3


class _FakeStream:
    """A subprocess pipe whose readline blocks forever (idle stdio server)."""

    async def readline(self) -> bytes:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class _FakeStdin:
    def write(self, data: bytes) -> None:
        pass

    async def drain(self) -> None:
        pass


class _FakeProc:
    def __init__(self) -> None:
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()
        self.stdin = _FakeStdin()
        self.returncode: int | None = None

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode or 0


class _FakeWS:
    """WS whose message iteration ends immediately with a clean close."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def close(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        pass


def test_run_session_returns_when_ws_closes_cleanly(monkeypatch) -> None:
    """A clean WS close must end the session even while stdio pumps are blocked.

    Regression: gather() waited for ALL pumps, so a normal-close from XiaoZhi
    (async-for ends without raising) left the session deadlocked on subprocess
    readline() forever and the reconnect loop never re-entered.
    """
    proc = _FakeProc()

    async def _fake_spawn(server_cmd):
        return proc

    monkeypatch.setattr(mcp_pipe, "_spawn_stdio_server", _fake_spawn)
    monkeypatch.setattr(mcp_pipe.websockets, "connect", lambda *a, **kw: _FakeWS())

    async def _run():
        await asyncio.wait_for(mcp_pipe._run_session("wss://x", ["python", "server.py"], "ua"), timeout=5)

    asyncio.run(_run())
    assert proc.returncode is not None  # finally-block terminated the child
