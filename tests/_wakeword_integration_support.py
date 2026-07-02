"""Shared support module for wakeword_runtime integration tests.

Loaded only by ``tests/test_wakeword_session_integration.py``. Hosts the
non-test plumbing necessary to (a) import the hyphenated on-disk path
``data/digital-human/wakeword_runtime/...`` via importlib + synthetic sys.modules
alias packages, and (b) a minimal hand-rolled WebSocket client used to drive
the server end-to-end.

Naming convention: leading ``_`` so pytest does NOT collect this as a test
module (its functions are imported, not discovered).
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import importlib.util
import os
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WAKEWORD_PKG_ROOT = ROOT / "data" / "digital-human" / "wakeword_runtime"
RUNTIME_DIR = WAKEWORD_PKG_ROOT / "runtime"
BRIDGE_DIR = WAKEWORD_PKG_ROOT / "bridge"

# Synthetic alias package names for the hyphen-shaped on-disk path. Relative
# imports inside http_server.py / frame_codec.py / bridge_request_handler.py /
# websocket_session.py / wakeword_config.py resolve against these.
WAKEWORD_ALIAS = "wakeword_runtime_pkg"
RUNTIME_ALIAS_PKG = WAKEWORD_ALIAS + ".runtime"
BRIDGE_ALIAS_PKG = WAKEWORD_ALIAS + ".bridge"


def _ensure_pkg(modname: str, path: Path) -> None:
    if modname in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        modname,
        path / "__init__.py",
        submodule_search_locations=[str(path)],
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)


def load_http_server_module() -> types.ModuleType:
    """Register the alias packages and return the loaded http_server module.

    Idempotent across multiple invocations (sys.modules caches everything).
    """
    if WAKEWORD_ALIAS not in sys.modules:
        pkg = types.ModuleType(WAKEWORD_ALIAS)
        pkg.__path__ = [str(WAKEWORD_PKG_ROOT)]  # type: ignore[attr-defined]
        sys.modules[WAKEWORD_ALIAS] = pkg

    if RUNTIME_ALIAS_PKG not in sys.modules:
        rp = types.ModuleType(RUNTIME_ALIAS_PKG)
        rp.__path__ = [str(RUNTIME_DIR)]  # type: ignore[attr-defined]
        sys.modules[RUNTIME_ALIAS_PKG] = rp

    if BRIDGE_ALIAS_PKG not in sys.modules:
        bp = types.ModuleType(BRIDGE_ALIAS_PKG)
        bp.__path__ = [str(BRIDGE_DIR)]  # type: ignore[attr-defined]
        sys.modules[BRIDGE_ALIAS_PKG] = bp
        # Force-load bridge.event_bridge so ..bridge resolves to the alias package's WakewordEventBridge.
        ev_spec = importlib.util.spec_from_file_location(
            BRIDGE_ALIAS_PKG + ".event_bridge", BRIDGE_DIR / "event_bridge.py"
        )
        assert ev_spec is not None and ev_spec.loader is not None
        ev_mod = importlib.util.module_from_spec(ev_spec)
        sys.modules[BRIDGE_ALIAS_PKG + ".event_bridge"] = ev_mod
        ev_spec.loader.exec_module(ev_mod)
        bp.WakewordEventBridge = ev_mod.WakewordEventBridge  # type: ignore[attr-defined]

    # Now load http_server.py under the runtime alias package path so its relative
    # import ``from ..bridge import WakewordEventBridge`` resolves to wakeword_runtime_pkg.bridge.
    spec = importlib.util.spec_from_file_location(
        RUNTIME_ALIAS_PKG + ".http_server",
        RUNTIME_DIR / "http_server.py",
    )
    assert spec is not None and spec.loader is not None
    http_server = importlib.util.module_from_spec(spec)
    sys.modules[RUNTIME_ALIAS_PKG + ".http_server"] = http_server
    spec.loader.exec_module(http_server)
    return http_server


# ── Minimal hand-rolled WebSocket client (RFC6455 frame subset) ──────────────
# Only the operations needed by the integration tests: send/receive text frames,
# masked-send (client→server per RFC), and upgrade handshake. Mirrors the
# server's frame_codec subset (text/ping/pong/close).


def ws_send_text(sock: socket.socket, message: str) -> None:
    """Server-style unmasked text frame (we never send client→server with this)."""
    payload = message.encode("utf-8")
    header = bytearray([0x81])
    if len(payload) < 126:
        header.append(len(payload))
    elif len(payload) < 65536:
        header.append(126)
        header.extend(len(payload).to_bytes(2, "big"))
    else:
        header.append(127)
        header.extend(len(payload).to_bytes(8, "big"))
    sock.sendall(bytes(header) + payload)


def ws_send_masked_text(sock: socket.socket, message: str) -> None:
    """Send a client-masked text frame (client→server MUST be masked per RFC6455)."""
    payload = message.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray([0x81])  # FIN + text opcode
    if len(payload) < 126:
        header.append(0x80 | len(payload))
    elif len(payload) < 65536:
        header.append(0x80 | 126)
        header.extend(len(payload).to_bytes(2, "big"))
    else:
        header.append(0x80 | 127)
        header.extend(len(payload).to_bytes(8, "big"))
    sock.sendall(bytes(header) + mask + masked)


def ws_read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("socket closed during ws read")
        buf.extend(chunk)
    return bytes(buf)


def ws_recv_text(sock: socket.socket) -> str | None:
    """Read one text frame. Returns None for close/ping/pong control frames."""
    header = ws_read_exact(sock, 2)
    first, second = header[0], header[1]
    opcode = first & 0x0F
    ln = second & 0x7F
    if ln == 126:
        ln = int.from_bytes(ws_read_exact(sock, 2), "big")
    elif ln == 127:
        ln = int.from_bytes(ws_read_exact(sock, 8), "big")
    payload = ws_read_exact(sock, ln) if ln else b""
    if opcode in (0x8, 0x9, 0xA):  # close / ping / pong
        return None
    if opcode != 0x1:
        return None
    return payload.decode("utf-8")


def ws_handshake(
    host: str,
    port: int,
    path: str = "/wakeword-ws",
    include_version: bool = True,
) -> socket.socket:
    """Perform RFC6455 client handshake and return the upgraded socket.

    ``include_version=False`` omits the ``Sec-WebSocket-Version: 13`` header,
    letting callers characterize the server's tolerance for its absence
    (current http_server contract: NOT validated → upgrade still succeeds).
    """
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    sock = socket.create_connection((host, port), timeout=5.0)
    version_line = "Sec-WebSocket-Version: 13\r\n" if include_version else ""
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"{version_line}"
        "\r\n"
    )
    sock.sendall(req.encode("ascii"))
    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(1024)
        if not chunk:
            sock.close()
            raise ConnectionError("handshake closed before completion")
        buf.extend(chunk)
    resp = bytes(buf)
    status_line = resp.split(b"\r\n", 1)[0].decode("ascii")
    if "101" not in status_line:
        sock.close()
        raise ConnectionError(f"unexpected handshake response: {status_line!r}")
    if f"sec-websocket-accept: {accept}".encode("ascii").lower() not in resp.lower():
        sock.close()
        raise ConnectionError("Sec-WebSocket-Accept mismatch")
    return sock
