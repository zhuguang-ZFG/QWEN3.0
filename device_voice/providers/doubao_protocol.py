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


def parse_response(res: bytes) -> dict:
    """Parse a Doubao binary protocol response frame."""
    protocol_version = res[0] >> 4
    header_size = res[0] & 0x0F
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0F
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0F
    _reserved = res[3]
    header_extensions = res[4 : header_size * 4]
    payload = res[header_size * 4 :]

    result: dict = {
        "protocol_version": protocol_version,
        "header_size": header_size,
        "message_type": message_type,
        "message_type_specific_flags": message_type_specific_flags,
        "serialization_method": serialization_method,
        "message_compression": message_compression,
        "header_extensions": header_extensions,
    }

    payload_msg = None
    payload_size = 0

    if message_type == SERVER_FULL_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result["seq"] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result["code"] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]

    if payload_msg is None:
        return result

    if message_compression == GZIP:
        payload_msg = gzip.decompress(payload_msg)
    if serialization_method == JSON:
        payload_msg = json.loads(payload_msg.decode("utf-8"))
    elif serialization_method != NO_SERIALIZATION:
        payload_msg = payload_msg.decode("utf-8")

    result["payload_msg"] = payload_msg
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
