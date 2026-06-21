"""Real-device smoke checks for LiMa firmware."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))

import ws_ticket_http


@dataclass(frozen=True)
class SmokeResult:
    name: str
    status: str
    message: str


async def run_hardware_smoke(host: str, device_id: str, token: str) -> SmokeResult:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("Install websockets to run hardware smoke") from exc

    ws_url = ws_ticket_http.ws_url_with_ticket(
        f"wss://{host}/device/v1/ws",
        ws_ticket_http.issue_device_ws_ticket(host, device_id, token),
    )
    hello = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": device_id,
        "fw_rev": "firmware-hardware-gate",
        "capabilities": ["audio", "run_path", "device_info", "self_check"],
    }
    async with websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaFirmwareGate/1.0"}) as ws:
        await ws.send(json.dumps(hello, ensure_ascii=False, separators=(",", ":")))
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
    ack = json.loads(raw)
    if ack.get("type") != "hello_ack":
        return SmokeResult("hardware_smoke", "fail", f"expected hello_ack, got {ack.get('type')}")
    return SmokeResult("hardware_smoke", "pass", "real /device/v1/ws hello_ack received")
