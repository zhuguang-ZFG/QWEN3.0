"""Regression tests for CORE-O2: mcp_pipe must back off when the stdio child dies.

A child that exits immediately (e.g. import error) closes its stdout, which
makes the bridge close the WS itself — that used to look like a clean session,
reset the reconnect delay and hot-loop a respawn every second. _run_session now
raises StdioServerExitedError in that case so run_bridge takes the
exponential-backoff branch. A genuine peer WS close (child alive) stays clean.
"""

from __future__ import annotations

import asyncio

import pytest

from dlc_mcp import mcp_pipe


class _BlockingOrEofStream:
    """stdout/stderr stand-in: immediate EOF when the child died, else blocks."""

    def __init__(self, eof: bool):
        self._eof = eof

    async def readline(self) -> bytes:
        if self._eof:
            return b""
        await asyncio.Event().wait()  # block until cancelled
        return b""

    def at_eof(self) -> bool:
        return self._eof


class _FakeStdin:
    def write(self, _data: bytes) -> None:
        pass

    async def drain(self) -> None:
        pass


class _FakeProc:
    def __init__(self, returncode: int | None):
        self.returncode = returncode
        dead = returncode is not None
        self.stdout = _BlockingOrEofStream(eof=dead)
        self.stderr = _BlockingOrEofStream(eof=dead)
        self.stdin = _FakeStdin()
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True
        if self.returncode is None:
            self.returncode = 0

    async def wait(self) -> int:
        return self.returncode if self.returncode is not None else 0


class _FakeWs:
    """WS stand-in; peer_closes controls whether the peer ends the session."""

    def __init__(self, peer_closes: bool):
        self._peer_closes = peer_closes
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def send(self, _text: str) -> None:
        pass

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if self._peer_closes:
            raise StopAsyncIteration
        await asyncio.Event().wait()  # peer keeps the connection open
        raise StopAsyncIteration


class _FakeConnectCM:
    def __init__(self, ws: _FakeWs):
        self._ws = ws

    async def __aenter__(self) -> _FakeWs:
        return self._ws

    async def __aexit__(self, *_args) -> bool:
        return False


def _patch_session(monkeypatch, proc: _FakeProc, ws: _FakeWs) -> None:
    async def fake_spawn(_cmd):
        return proc

    def fake_connect(_endpoint, additional_headers=None, extra_headers=None):
        return _FakeConnectCM(ws)

    monkeypatch.setattr(mcp_pipe, "_spawn_stdio_server", fake_spawn)
    monkeypatch.setattr(mcp_pipe.websockets, "connect", fake_connect)


def test_child_exit_raises_backoff_error(monkeypatch):
    """Child died at startup (stdout EOF) -> StdioServerExitedError, not clean."""
    proc = _FakeProc(returncode=1)
    _patch_session(monkeypatch, proc, _FakeWs(peer_closes=False))
    with pytest.raises(mcp_pipe.StdioServerExitedError, match="returncode=1"):
        asyncio.run(mcp_pipe._run_session("ws://test", ["cmd"], "ua"))


def test_peer_close_with_live_child_is_clean(monkeypatch):
    """Peer closed the WS while the child is alive -> clean session, no raise."""
    proc = _FakeProc(returncode=None)
    _patch_session(monkeypatch, proc, _FakeWs(peer_closes=True))
    asyncio.run(mcp_pipe._run_session("ws://test", ["cmd"], "ua"))
    assert proc.terminated  # cleanup still terminates the child
