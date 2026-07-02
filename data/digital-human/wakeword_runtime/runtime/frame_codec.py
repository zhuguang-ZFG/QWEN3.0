"""WebSocket 帧编解码纯函数（RFC6455 最小子集）。

ponytail: 不依赖 self/socket/connection，只接受 reader(.recv)/writer(.write/.flush)，
便于单测；上限是仅实现 RFC6455 最小帧子集（无分片/无 RSV），覆盖唤醒词 runtime
实际用到的 text/ping/pong/close 帧。升级路径：若需分片或合规审计，换用 wsproto。
"""

from __future__ import annotations

import base64
import hashlib
import socket

# RFC6455 section 1.3 handshake magic GUID (appended to client key for accept).
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes (RFC6455 section 5.2).
_OPCODE_CONTINUATION = 0x0
_OPCODE_TEXT = 0x1
_OPCODE_BINARY = 0x2
_OPCODE_CLOSE = 0x8
_OPCODE_PING = 0x9
_OPCODE_PONG = 0xA


def compute_accept(websocket_key: str) -> str:
    """Return the Sec-WebSocket-Accept value for a client Sec-WebSocket-Key.

    Per RFC6455 section 1.3: base64(sha1(key + GUID)).
    """
    accept_source = websocket_key + _WS_GUID
    digest = hashlib.sha1(accept_source.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def read_exact(reader, size: int) -> bytes:
    """Read exactly ``size`` bytes from ``reader.recv`` or raise on short EOF.

    ``reader`` must expose ``recv(size) -> bytes`` (e.g. a raw socket).
    Returns b"" immediately when ``size <= 0``.
    Raises ``ConnectionResetError`` if the peer closes before all bytes arrive.
    """
    if size <= 0:
        return b""

    chunks = bytearray()
    while len(chunks) < size:
        chunk = reader.recv(size - len(chunks))
        if not chunk:
            raise ConnectionResetError("websocket connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def receive_message(reader, writer) -> str | None:
    """Read one WebSocket frame from ``reader`` and decode per opcode.

    - text frame (0x1): returns the decoded utf-8 string payload.
    - ping (0x9): writes a pong frame (0xA) to ``writer``, returns None.
    - pong (0xA): returns None (consumed).
    - close (0x8): raises ``ConnectionAbortedError``.
    - continuation(0x0)/binary(0x2)/reserved: returns None (ignored).
    - On socket timeout reading the frame header: returns None.

    Caller is responsible for writer.flush() — ``send_frame`` calls it itself.
    """
    try:
        header = read_exact(reader, 2)
    except socket.timeout:
        return None

    first_byte, second_byte = header[0], header[1]
    opcode = first_byte & 0x0F
    masked = (second_byte & 0x80) != 0
    payload_length = second_byte & 0x7F

    if payload_length == 126:
        payload_length = int.from_bytes(read_exact(reader, 2), "big")
    elif payload_length == 127:
        payload_length = int.from_bytes(read_exact(reader, 8), "big")

    masking_key = read_exact(reader, 4) if masked else b""
    payload = read_exact(reader, payload_length) if payload_length else b""

    if masked and payload:
        payload = bytes(byte ^ masking_key[index % 4] for index, byte in enumerate(payload))

    if opcode == _OPCODE_CLOSE:
        raise ConnectionAbortedError("websocket closed by client")

    if opcode == _OPCODE_PING:
        send_frame(writer, _OPCODE_PONG, payload)
        return None

    if opcode == _OPCODE_PONG:
        return None

    if opcode != _OPCODE_TEXT:
        return None

    return payload.decode("utf-8")


def send_frame(writer, opcode: int, payload: bytes) -> None:
    """Write one unmasked WebSocket frame to ``writer`` (e.g. ``self.wfile``).

    Frames sent by the server are unmasked (RFC6455 section 5.3 — only clients mask).
    Handles the three payload-length encodings: 7-bit, 16-bit (126), 64-bit (127).
    Calls ``writer.flush()`` after writing so callers need not.
    """
    header = bytearray()
    header.append(0x80 | opcode)  # FIN=1, RSV=0, opcode

    payload_length = len(payload)
    if payload_length < 126:
        header.append(payload_length)
    elif payload_length < 65536:
        header.append(126)
        header.extend(payload_length.to_bytes(2, "big"))
    else:
        header.append(127)
        header.extend(payload_length.to_bytes(8, "big"))

    writer.write(bytes(header) + payload)
    writer.flush()


def send_text(writer, message: str) -> None:
    """Send a text frame with the utf-8 encoded ``message``."""
    send_frame(writer, _OPCODE_TEXT, message.encode("utf-8"))
