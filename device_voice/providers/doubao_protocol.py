"""Shared binary protocol helpers for Volcano Engine / Doubao speech APIs.

This is a private module used by the Doubao ASR/TTS providers. The protocol
matches the reference implementation in xiaozhi-server.
"""

from __future__ import annotations

import gzip
import json


# Message types
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010

NO_SEQUENCE = 0b0000
NEG_SEQUENCE = 0b0010

SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Serialization / compression
NO_SERIALIZATION = 0b0000
JSON = 0b0001
NO_COMPRESSION = 0b0000
GZIP = 0b0001


def _parse_frame_header(res: bytes) -> tuple[dict, bytes]:
    """Parse the fixed header and return (header_dict, payload_bytes)."""
    header_size = res[0] & 0x0F
    return {
        "protocol_version": res[0] >> 4,
        "header_size": header_size,
        "message_type": res[1] >> 4,
        "message_type_specific_flags": res[1] & 0x0F,
        "serialization_method": res[2] >> 4,
        "message_compression": res[2] & 0x0F,
        "header_extensions": res[4 : header_size * 4],
    }, res[header_size * 4 :]


def _extract_payload(message_type: int, payload: bytes) -> tuple[bytes | None, int, dict]:
    """Return (payload_msg, payload_size, extra_fields) for a known message type."""
    if message_type == SERVER_FULL_RESPONSE:
        return payload[4:], int.from_bytes(payload[:4], "big", signed=True), {}
    if message_type == SERVER_ACK:
        extra = {"seq": int.from_bytes(payload[:4], "big", signed=True)}
        if len(payload) >= 8:
            return payload[8:], int.from_bytes(payload[4:8], "big", signed=False), extra
        return None, 0, extra
    if message_type == SERVER_ERROR_RESPONSE:
        extra = {"code": int.from_bytes(payload[:4], "big", signed=False)}
        return payload[8:], int.from_bytes(payload[4:8], "big", signed=False), extra
    return None, 0, {}


def _decode_payload_msg(payload_msg: bytes, serialization_method: int, message_compression: int) -> object:
    """Decompress and deserialize payload bytes according to the header flags."""
    if message_compression == GZIP:
        payload_msg = gzip.decompress(payload_msg)
    if serialization_method == JSON:
        return json.loads(payload_msg.decode("utf-8"))
    if serialization_method != NO_SERIALIZATION:
        return payload_msg.decode("utf-8")
    return payload_msg


def parse_response(res: bytes) -> dict:
    """Parse a Doubao binary protocol response frame."""
    result, payload = _parse_frame_header(res)
    payload_msg, payload_size, extra = _extract_payload(result["message_type"], payload)
    result.update(extra)

    if payload_msg is None:
        return result

    result["payload_msg"] = _decode_payload_msg(
        payload_msg, result["serialization_method"], result["message_compression"]
    )
    result["payload_size"] = payload_size
    return result


def generate_header(
    message_type: int = CLIENT_FULL_REQUEST,
    message_type_specific_flags: int = NO_SEQUENCE,
    serialization_method: int = JSON,
    compression_type: int = GZIP,
) -> bytearray:
    """Generate a Doubao protocol request header."""
    header_size = 1
    header = bytearray()
    header.append((0b0001 << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serialization_method << 4) | compression_type)
    header.append(0x00)
    return header


def build_request_frame(payload: dict, *, is_audio: bool = False, is_last: bool = False) -> bytes:
    """Build a complete request frame from a JSON payload."""
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    payload_bytes = gzip.compress(payload_bytes)

    flags = NEG_SEQUENCE if is_last else NO_SEQUENCE
    msg_type = CLIENT_AUDIO_ONLY_REQUEST if is_audio else CLIENT_FULL_REQUEST
    header = generate_header(message_type=msg_type, message_type_specific_flags=flags)
    header.extend(len(payload_bytes).to_bytes(4, "big"))
    header.extend(payload_bytes)
    return bytes(header)


def build_audio_frame(audio_bytes: bytes, *, is_last: bool = False) -> bytes:
    """Build an audio-only frame containing raw PCM bytes."""
    payload_bytes = gzip.compress(audio_bytes)
    flags = NEG_SEQUENCE if is_last else NO_SEQUENCE
    header = generate_header(message_type=CLIENT_AUDIO_ONLY_REQUEST, message_type_specific_flags=flags)
    header.extend(len(payload_bytes).to_bytes(4, "big"))
    header.extend(payload_bytes)
    return bytes(header)
