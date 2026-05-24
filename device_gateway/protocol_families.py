"""Device Gateway protocol family schemas.

Each protocol family (motion, display, audio, speech, ocr, camera,
perception) has a separate schema and allowlist. Families are default-off
until safety evidence and per-family approval gates pass.

Only the writing-machine `motion_task` family is currently active.
All other families remain gated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProtocolFamily(str, Enum):
    MOTION = "motion"
    DISPLAY = "display"
    AUDIO = "audio"
    SPEECH = "speech"
    OCR = "ocr"
    CAMERA = "camera"
    PERCEPTION = "perception"


class MotionErrorCode(str, Enum):
    E_UNSUPPORTED_CAPABILITY = "E_UNSUPPORTED_CAPABILITY"
    E_MISSING_PATH = "E_MISSING_PATH"
    E_BAD_PARAMS = "E_BAD_PARAMS"
    E_U1_UNAVAILABLE = "E_U1_UNAVAILABLE"
    E_DEVICE_UPDATING = "E_DEVICE_UPDATING"
    E_EXECUTION_FAILED = "E_EXECUTION_FAILED"
    E_UNSUPPORTED_BOARD = "E_UNSUPPORTED_BOARD"
    E_TIMEOUT = "E_TIMEOUT"


FAMILY_ALLOWLISTS: dict[str, frozenset[str]] = {
    ProtocolFamily.MOTION.value: frozenset({"run_path", "write_text", "draw_generated"}),
    ProtocolFamily.DISPLAY.value: frozenset({"show_image", "show_text", "clear_screen"}),
    ProtocolFamily.AUDIO.value: frozenset({"play_audio", "stop_audio", "set_volume"}),
    ProtocolFamily.SPEECH.value: frozenset({"tts_speak", "voice_clone"}),
    ProtocolFamily.OCR.value: frozenset({"capture_text", "read_display"}),
    ProtocolFamily.CAMERA.value: frozenset({"capture_frame", "stream_start", "stream_stop"}),
    ProtocolFamily.PERCEPTION.value: frozenset({"wifi_csi_sample", "presence_detect"}),
}

ACTIVE_FAMILIES: frozenset[str] = frozenset({ProtocolFamily.MOTION.value})

GATED_FAMILIES: frozenset[str] = frozenset({
    ProtocolFamily.DISPLAY.value, ProtocolFamily.AUDIO.value,
    ProtocolFamily.SPEECH.value, ProtocolFamily.OCR.value,
    ProtocolFamily.CAMERA.value, ProtocolFamily.PERCEPTION.value,
})


@dataclass
class ProtocolSchema:
    family: str
    capability: str
    params_schema: dict = field(default_factory=dict)


MOTION_SCHEMAS = [
    ProtocolSchema("motion", "run_path", {
        "feed": {"type": "int", "required": True},
        "path": {"type": "array", "required": True},
    }),
    ProtocolSchema("motion", "write_text", {
        "feed": {"type": "int", "required": True},
        "text": {"type": "string", "required": True, "max_length": 80},
    }),
    ProtocolSchema("motion", "draw_generated", {
        "feed": {"type": "int", "required": True},
        "prompt": {"type": "string", "required": True, "max_length": 120},
    }),
]

DISPLAY_SCHEMAS = [
    ProtocolSchema("display", "show_image", {
        "url": {"type": "string", "required": True},
    }),
    ProtocolSchema("display", "show_text", {
        "text": {"type": "string", "required": True, "max_length": 200},
    }),
]

AUDIO_SCHEMAS = [
    ProtocolSchema("audio", "play_audio", {
        "url": {"type": "string", "required": True},
        "loop": {"type": "bool", "required": False},
    }),
]

SPEECH_SCHEMAS = [
    ProtocolSchema("speech", "tts_speak", {
        "text": {"type": "string", "required": True, "max_length": 500},
        "voice": {"type": "string", "required": False},
    }),
]

OCR_SCHEMAS = [
    ProtocolSchema("ocr", "capture_text", {
        "region": {"type": "object", "required": False},
    }),
]

CAMERA_SCHEMAS = [
    ProtocolSchema("camera", "capture_frame", {
        "resolution": {"type": "string", "required": False},
    }),
]

PERCEPTION_SCHEMAS = [
    ProtocolSchema("perception", "wifi_csi_sample", {
        "duration_ms": {"type": "int", "required": False, "max": 5000},
    }),
]

ALL_SCHEMAS: dict[str, list[ProtocolSchema]] = {
    ProtocolFamily.MOTION.value: MOTION_SCHEMAS,
    ProtocolFamily.DISPLAY.value: DISPLAY_SCHEMAS,
    ProtocolFamily.AUDIO.value: AUDIO_SCHEMAS,
    ProtocolFamily.SPEECH.value: SPEECH_SCHEMAS,
    ProtocolFamily.OCR.value: OCR_SCHEMAS,
    ProtocolFamily.CAMERA.value: CAMERA_SCHEMAS,
    ProtocolFamily.PERCEPTION.value: PERCEPTION_SCHEMAS,
}


def _family_value(family: str | ProtocolFamily) -> str:
    return family.value if isinstance(family, ProtocolFamily) else family


def family_is_active(family: str | ProtocolFamily) -> bool:
    return _family_value(family) in ACTIVE_FAMILIES


def family_capabilities(family: str | ProtocolFamily) -> frozenset[str]:
    return FAMILY_ALLOWLISTS.get(_family_value(family), frozenset())


def validate_capability(family: str | ProtocolFamily, capability: str) -> bool:
    if not family_is_active(family):
        return False
    allowed = family_capabilities(family)
    if not allowed:
        return False
    return capability in allowed
