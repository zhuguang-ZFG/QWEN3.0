"""Short-lived probe: bridge dlc_mcp/server.py to XiaoZhi official MCP endpoint.

Usage (token via env — never commit):
  $env:MCP_ENDPOINT = 'wss://api.xiaozhi.me/mcp/?token=...'
  .\\.venv310\\Scripts\\python.exe scripts/probe_xiaozhi_mcp_e2e.py --seconds 25

Prints summarized JSON-RPC traffic (methods + isError on tool results).
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "dlc_mcp" / "server.py"


def _header_kwargs(connect_func, headers: dict[str, str]) -> dict:
    params = inspect.signature(connect_func).parameters
    if "additional_headers" in params:
        return {"additional_headers": headers}
    return {"extra_headers": headers}


def _safe_print(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"), flush=True)


def _summarize(text: str, direction: str) -> str | None:
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return f"{direction} non-json: {text[:120]!r}"
    if not isinstance(msg, dict):
        return None
    method = msg.get("method")
    if method:
        return f"{direction} -> method={method!r} id={msg.get('id')!r}"
    if "result" in msg:
        result = msg.get("result")
        extra = ""
        if isinstance(result, dict) and "content" in result:
            extra = f" isError={result.get('isError')!r}"
        return f"{direction} <- result id={msg.get('id')!r}{extra}"
    if "error" in msg:
        err = msg["error"]
        return f"{direction} <- error id={msg.get('id')!r} code={err.get('code')}"
    return f"{direction} {list(msg.keys())}"


async def _spawn_server() -> asyncio.subprocess.Process:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return await asyncio.create_subprocess_exec(
        sys.executable,
        str(SERVER),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT),
        env=env,
    )


async def _terminate_proc(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=3)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _stderr_reader(proc: asyncio.subprocess.Process, errors: list[str]) -> None:
    assert proc.stderr is not None
    while True:
        line = await proc.stderr.readline()
        if not line:
            return
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            errors.append(text)


async def _stdio_to_ws(proc: asyncio.subprocess.Process, ws, lines: list[str]) -> None:
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            await ws.close()
            return
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        summary = _summarize(text, "out")
        if summary:
            lines.append(summary)
        await ws.send(text)


async def _inject_tools_call(proc: asyncio.subprocess.Process, lines: list[str]) -> None:
    assert proc.stdin is not None
    fake_call = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": "dlc.get_device_status", "arguments": {"device_id": "dev-probe"}},
    }
    lines.append("inject -> tools/call dlc.get_device_status")
    proc.stdin.write((json.dumps(fake_call, ensure_ascii=False) + "\n").encode("utf-8"))
    await proc.stdin.drain()


async def _ws_to_stdio(
    proc: asyncio.subprocess.Process,
    ws,
    lines: list[str],
    *,
    inject_tools_call: bool,
    injected: dict[str, bool],
) -> None:
    assert proc.stdin is not None
    async for message in ws:
        if isinstance(message, bytes):
            continue
        summary = _summarize(message, "in")
        if summary:
            lines.append(summary)
        proc.stdin.write(message.encode("utf-8") + b"\n")
        await proc.stdin.drain()
        if not inject_tools_call or injected["done"]:
            continue
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            continue
        if msg.get("method") == "tools/list":
            injected["done"] = True
            await _inject_tools_call(proc, lines)


def _print_report(lines: list[str], errors: list[str]) -> None:
    _safe_print("--- traffic ---")
    for line in lines[:40]:
        _safe_print(line)
    if len(lines) > 40:
        _safe_print(f"... ({len(lines) - 40} more)")
    if errors:
        _safe_print("--- stderr (tail) ---")
        for e in errors[-8:]:
            _safe_print(e)


async def _probe(endpoint: str, seconds: float, *, inject_tools_call: bool) -> int:
    proc = await _spawn_server()
    lines: list[str] = []
    errors: list[str] = []
    injected = {"done": False}
    try:
        async with websockets.connect(
            endpoint,
            **_header_kwargs(websockets.connect, {"User-Agent": "LiMa-DLC-MCP-probe/0.1"}),
        ) as ws:
            _safe_print("CONNECTED")
            await asyncio.wait_for(
                asyncio.gather(
                    _stdio_to_ws(proc, ws, lines),
                    _ws_to_stdio(proc, ws, lines, inject_tools_call=inject_tools_call, injected=injected),
                    _stderr_reader(proc, errors),
                ),
                timeout=seconds,
            )
    except asyncio.TimeoutError:
        _safe_print(f"SESSION_OK timeout={seconds}s (normal for probe)")
    except Exception as exc:
        _safe_print(f"SESSION_FAIL {type(exc).__name__}: {exc}")
        for e in errors[-5:]:
            _safe_print(f"stderr: {e}")
        return 1
    finally:
        await _terminate_proc(proc)
    _print_report(lines, errors)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=os.environ.get("MCP_ENDPOINT", ""))
    parser.add_argument("--seconds", type=float, default=25.0)
    parser.add_argument(
        "--inject-tools-call",
        action="store_true",
        help="After cloud tools/list, inject dlc.get_device_status to verify isError on result",
    )
    args = parser.parse_args()
    if not args.endpoint:
        print("Set MCP_ENDPOINT or --endpoint", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_probe(args.endpoint, args.seconds, inject_tools_call=args.inject_tools_call)))


if __name__ == "__main__":
    main()
