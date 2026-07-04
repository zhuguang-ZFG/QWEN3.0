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


def _websocket_header_kwargs(connect_func: Any, headers: dict[str, str]) -> dict[str, dict[str, str]]:
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
    return await asyncio.create_subprocess_exec(
        *server_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _stdio_to_ws(proc: asyncio.subprocess.Process, ws: websockets.WebSocketClientProtocol) -> None:
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


async def _ws_to_stdio(ws: websockets.WebSocketClientProtocol, proc: asyncio.subprocess.Process) -> None:
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


async def run_bridge(endpoint: str, server_cmd: list[str], user_agent: str) -> int:
    if not endpoint:
        print("missing MCP endpoint; set --endpoint or MCP_ENDPOINT", file=sys.stderr)
        return 2

    proc = await _spawn_stdio_server(server_cmd)
    headers = {"User-Agent": user_agent}

    try:
        async with websockets.connect(endpoint, **_websocket_header_kwargs(websockets.connect, headers)) as ws:
            await asyncio.gather(
                _stdio_to_ws(proc, ws),
                _ws_to_stdio(ws, proc),
                _stderr_logger(proc),
            )
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
    return 0


def main() -> None:
    args = build_arg_parser().parse_args()
    server_cmd = args.server_cmd or _default_server_cmd()
    raise SystemExit(asyncio.run(run_bridge(args.endpoint, server_cmd, args.user_agent)))


if __name__ == "__main__":
    main()
