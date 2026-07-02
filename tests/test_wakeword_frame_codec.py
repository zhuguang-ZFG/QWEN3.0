"""Tests for wakeword_runtime WebSocket frame codec (pure-function module).

Loaded via importlib because the on-disk path ``data/digital-human/...`` is not
a valid Python package name (hyphen), mirroring the pattern used by
``test_jdcloud_push_probe.py``.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

CODEC_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "digital-human"
    / "wakeword_runtime"
    / "runtime"
    / "frame_codec.py"
)

_spec = importlib.util.spec_from_file_location("frame_codec", CODEC_PATH)
assert _spec is not None
assert _spec.loader is not None
frame_codec = importlib.util.module_from_spec(_spec)
sys.modules["frame_codec"] = frame_codec
_spec.loader.exec_module(frame_codec)


# ── helpers ─────────────────────────────────────────────────────────────────


class _FakeReader:
    """Minimal reader exposing only ``recv`` like a real socket."""

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0

    def recv(self, size: int) -> bytes:
        if self._pos >= len(self._data):
            return b""
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


# RFC6455 section 1.3 canonical example. The magic GUID is appended by
# ``compute_accept`` itself, so we feed only the client key.
_RFC_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
_RFC_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


# ── compute_accept ───────────────────────────────────────────────────────────


def test_compute_accept_known_vector() -> None:
    """RFC6455 sample vector must round-trip exactly."""
    assert frame_codec.compute_accept(_RFC_KEY) == _RFC_ACCEPT


# ── read_exact ────────────────────────────────────────────────────────────────


def test_read_exact_short_eof_raises_reset() -> None:
    """A truncated stream must raise ConnectionResetError, not return short."""
    reader = _FakeReader(b"ab")
    with pytest.raises(ConnectionResetError):
        frame_codec.read_exact(reader, 5)


def test_read_exact_full() -> None:
    reader = _FakeReader(b"hello")
    assert frame_codec.read_exact(reader, 5) == b"hello"


def test_read_exact_zero_returns_empty() -> None:
    reader = _FakeReader(b"")
    assert frame_codec.read_exact(reader, 0) == b""


# ── receive_message ───────────────────────────────────────────────────────────


def test_receive_text_frame_unmasked() -> None:
    # 0x81 = FIN + text(0x1); 0x05 = len 5; payload "hello"
    reader = _FakeReader(b"\x81\x05hello")
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) == "hello"


def test_receive_text_frame_masked_unmask() -> None:
    # masked: 0x81 0x85 + 4-byte mask + masked payload "world"
    mask = b"\x11\x22\x33\x44"
    payload = b"world"
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame = b"\x81\x85" + mask + masked
    reader = _FakeReader(frame)
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) == "world"


def test_receive_ping_emits_pong_returns_None() -> None:
    # 0x89 = FIN + ping(0x9); 0x04 = len 4; payload "ping"
    reader = _FakeReader(b"\x89\x04ping")
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) is None
    sent = writer.getvalue()
    # first byte opcode 0x8A (FIN+pong), len 4, payload "ping"
    assert sent == b"\x8a\x04ping"


def test_receive_close_raises_ConnectionAbortedError() -> None:
    # 0x88 = FIN + close(0x8)
    reader = _FakeReader(b"\x88\x00")
    writer = io.BytesIO()
    with pytest.raises(ConnectionAbortedError):
        frame_codec.receive_message(reader, writer)


def test_receive_pong_returns_None() -> None:
    # 0x8A = FIN + pong(0xA)
    reader = _FakeReader(b"\x8a\x00")
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) is None


def test_receive_unknown_opcode_returns_None() -> None:
    # opcode 0x3 (reserved) FIN set
    reader = _FakeReader(b"\x83\x00")
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) is None


def test_receive_extended_length_126() -> None:
    payload = b"x" * 130
    reader = _FakeReader(b"\x81\x7e" + (130).to_bytes(2, "big") + payload)
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) == "x" * 130


def test_receive_empty_payload_text() -> None:
    # 0x81 0x00 — empty text frame
    reader = _FakeReader(b"\x81\x00")
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) == ""


# ── send_frame / send_text ────────────────────────────────────────────────────


def test_send_text_small() -> None:
    writer = io.BytesIO()
    frame_codec.send_text(writer, "hi")
    assert writer.getvalue() == b"\x81\x02hi"


def test_send_frame_medium_payload_126() -> None:
    payload = b"a" * 200  # > 125 -> uses 2-byte length
    writer = io.BytesIO()
    frame_codec.send_frame(writer, 0x1, payload)
    out = writer.getvalue()
    assert out[0] == 0x81
    assert out[1] == 126
    assert int.from_bytes(out[2:4], "big") == 200
    assert out[4:] == payload


def test_send_frame_large_payload_127() -> None:
    payload = b"b" * 70000  # > 65535 -> uses 8-byte length
    writer = io.BytesIO()
    frame_codec.send_frame(writer, 0x1, payload)
    out = writer.getvalue()
    assert out[0] == 0x81
    assert out[1] == 127
    assert int.from_bytes(out[2:10], "big") == 70000
    assert out[10:] == payload


def test_send_roundtrip() -> None:
    """Send then receive should reproduce the original text (unmasked)."""
    reader_buf = io.BytesIO()
    frame_codec.send_text(reader_buf, "round-trip hello")
    reader = _FakeReader(reader_buf.getvalue())
    writer = io.BytesIO()
    assert frame_codec.receive_message(reader, writer) == "round-trip hello"
