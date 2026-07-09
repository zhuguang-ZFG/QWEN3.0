"""On-disk audio clip storage for device-app voiceprint playback."""

from __future__ import annotations

import re
from pathlib import Path

from config.db_config import get_lima_data_dir

_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_id(value: str) -> str:
    cleaned = _SAFE_ID.sub("_", (value or "").strip())
    if not cleaned:
        raise ValueError("audio id is required")
    return cleaned


def audio_root() -> Path:
    return Path(get_lima_data_dir()) / "device-app-audio"


def audio_file_path(device_id: str, audio_id: str, *, ext: str = "mp3") -> Path:
    safe_device = _sanitize_id(device_id)
    safe_audio = _sanitize_id(audio_id)
    safe_ext = _sanitize_id(ext).lstrip(".") or "mp3"
    return audio_root() / safe_device / f"{safe_audio}.{safe_ext}"


def ext_for_content_type(content_type: str) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
    }.get(normalized, "bin")


def write_audio_file(device_id: str, audio_id: str, data: bytes, *, ext: str = "mp3") -> str:
    path = audio_file_path(device_id, audio_id, ext=ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path.relative_to(audio_root()))


def resolve_storage_path(storage_path: str) -> Path | None:
    relative = Path((storage_path or "").strip())
    if not relative.parts or ".." in relative.parts:
        return None
    path = (audio_root() / relative).resolve()
    root = audio_root().resolve()
    if not str(path).startswith(str(root)):
        return None
    return path if path.is_file() else None
