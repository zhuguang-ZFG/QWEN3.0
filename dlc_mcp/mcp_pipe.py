"""WebSocket bridge that connects a stdio MCP server to XiaoZhi's MCP endpoint."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import os
import sys
from pathlib import Path
from typing import Any

import websockets

DEFAULT_ENDPOINT_ENV = "MCP_ENDPOINT"
DEFAULT_SERVER = str(Path(__file__).with_name("server.py"))
_REPO_ROOT = str(Path(__file__).resolve().parents[1])


def _websocket_header_kwargs(connect_func: Any, headers: dict[str, str]) -> dict[str, Any]:
    params = inspect.signature(connect_func).parameters
    if "additional_headers" in params:
        return {"additional_headers": headers}
    return {"extra_headers": headers}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge a stdio MCP server to a XiaoZhi WebSocket MCP endpoint")
    parser.add_argument(
        "server_cmd", nargs=argparse.REMAINDER, help="stdio MCP server command (default: python dlc_mcp/server.py)"
    )
    parser.add_argument(
        "--endpoint", default=os.environ.get(DEFAULT_ENDPOINT_ENV, ""), help="WebSocket MCP endpoint URL"
    )
    parser.add_argument("--user-agent", default="LiMa-DLC-MCP/0.1.0-p0")
    return parser


def _default_server_cmd() -> list[str]:
    return [sys.executable, DEFAULT_SERVER]


async def _spawn_stdio_server(server_cmd: list[str]) -> asyncio.subprocess.Process:
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return await asyncio.create_subprocess_exec(
        *server_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=_REPO_ROOT,
        env=env,
    )


async def _stdio_to_ws(proc: asyncio.subprocess.Process, ws: Any) -> None:
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            await ws.close()
            return
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        await ws.send(text)


async def _ws_to_stdio(ws: Any, proc: asyncio.subprocess.Process) -> None:
    assert proc.stdin is not None
    async for message in ws:
        if isinstance(message, bytes):
            continue
        proc.stdin.write(message.encode("utf-8") + b"\n")
        await proc.stdin.drain()


async def _stderr_logger(proc: asyncio.subprocess.Process) -> None:
    assert proc.stderr is not None
    while True:
        line = await proc.stderr.readline()
        if not line:
            return
        sys.stderr.write(line.decode("utf-8", errors="replace"))
        sys.stderr.flush()


# Reconnect backoff bounds (seconds). XiaoZhi closes idle MCP connections, so a
# single session ending is normal — we reconnect instead of crashing out.
_RECONNECT_MIN_DELAY = 1.0
_RECONNECT_MAX_DELAY = 30.0


class StdioServerExitedError(RuntimeError):
    """Stdio MCP server exited on its own (e.g. import error at startup).

    CORE-O2: a child that dies immediately makes the session *look* clean
    (stdout EOF -> we close the WS ourselves), which used to reset the
    reconnect delay and hot-loop a respawn every second. Raising instead sends
    run_bridge down the exponential-backoff branch.
    """


async def _run_session(endpoint: str, server_cmd: list[str], user_agent: str) -> None:
    """Run one bridge session: spawn a fresh stdio server, connect, pump until WS closes."""
    proc = await _spawn_stdio_server(server_cmd)
    headers = {"User-Agent": user_agent}
    try:
        async with websockets.connect(endpoint, **_websocket_header_kwargs(websockets.connect, headers)) as ws:
            # First-completed wins: a clean WS close ends _ws_to_stdio without an
            # exception while the other pumps stay blocked on subprocess pipes, so
            # gather() would hang the session forever. Cancel the survivors instead.
            pumps = [
                asyncio.ensure_future(_stdio_to_ws(proc, ws)),
                asyncio.ensure_future(_ws_to_stdio(ws, proc)),
                asyncio.ensure_future(_stderr_logger(proc)),
            ]
            try:
                done, pending = await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    task.result()  # re-raise pump errors so run_bridge backs off
            finally:
                for task in pumps:
                    task.cancel()
        # CORE-O2: pumps ended without an error. If the child already died
        # (returncode set, or stdout at EOF before the watcher reaped it), the
        # session was ended by the child — not a clean peer close. Raise so
        # run_bridge backs off instead of resetting the delay.
        if proc.returncode is not None or (proc.stdout is not None and proc.stdout.at_eof()):
            raise StdioServerExitedError(f"stdio server exited early (returncode={proc.returncode})")
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


async def run_bridge(endpoint: str, server_cmd: list[str], user_agent: str) -> int:
    if not endpoint:
        print("missing MCP endpoint; set --endpoint or MCP_ENDPOINT", file=sys.stderr)
        return 2

    delay = _RECONNECT_MIN_DELAY
    while True:
        try:
            await _run_session(endpoint, server_cmd, user_agent)
            # Clean session end (WS closed by peer) — reset backoff and reconnect.
            delay = _RECONNECT_MIN_DELAY
        except asyncio.CancelledError:
            # systemd stop / KeyboardInterrupt — exit the loop cleanly.
            raise
        except Exception as exc:
            print(f"bridge session ended: {type(exc).__name__}: {exc}; reconnecting in {delay:.0f}s", file=sys.stderr)
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)
            continue
        # Brief pause before reconnecting after a clean close to avoid a tight loop.
        await asyncio.sleep(_RECONNECT_MIN_DELAY)


def main() -> None:
    args = build_arg_parser().parse_args()
    server_cmd = args.server_cmd or _default_server_cmd()
    try:
        raise SystemExit(asyncio.run(run_bridge(args.endpoint, server_cmd, args.user_agent)))
    except KeyboardInterrupt:
        raise SystemExit(0) from None


if __name__ == "__main__":
    main()
