"""Device shadow state updated from gateway uplink messages."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any


@dataclass
class DeviceShadow:
    device_id: str
    fw_rev: str = ""
    capabilities: list[str] = field(default_factory=list)
    profile_id: str = ""
    last_heartbeat_uptime_ms: int = 0
    device_info: dict[str, Any] = field(default_factory=dict)
    self_check: dict[str, Any] = field(default_factory=dict)
    last_motion_event: dict[str, Any] = field(default_factory=dict)
    voiceprint_sample: dict[str, Any] = field(default_factory=dict)
    voiceprint_result: dict[str, Any] = field(default_factory=dict)
    desired: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: _now_iso())

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "fw_rev": self.fw_rev,
            "capabilities": list(self.capabilities),
            "profile_id": self.profile_id,
            "last_heartbeat_uptime_ms": self.last_heartbeat_uptime_ms,
            "device_info": deepcopy(self.device_info),
            "self_check": deepcopy(self.self_check),
            "last_motion_event": deepcopy(self.last_motion_event),
            "desired": deepcopy(self.desired),
            "updated_at": self.updated_at,
        }


class DeviceShadowStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._shadows: dict[str, DeviceShadow] = {}
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._shadows.clear()

    def update_hello(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.fw_rev = str(message.get("fw_rev", ""))
            shadow.capabilities = sorted(set(str(item) for item in message.get("capabilities", [])))
            shadow.profile_id = str(message.get("profile_id", shadow.profile_id))
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_heartbeat(self, device_id: str, uptime_ms: int) -> dict[str, Any]:
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.last_heartbeat_uptime_ms = int(uptime_ms)
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_device_info(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.device_info = deepcopy({k: v for k, v in message.items() if k not in {"type", "request_id"}})
            if not shadow.profile_id and isinstance(message.get("model"), str):
                shadow.profile_id = str(message["model"])
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_self_check(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.self_check = deepcopy({k: v for k, v in message.items() if k not in {"type", "request_id"}})
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_motion_event(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.last_motion_event = deepcopy({k: v for k, v in message.items() if k != "type"})
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_voiceprint_sample(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.voiceprint_sample = deepcopy({k: v for k, v in message.items() if k not in {"type", "request_id"}})
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def update_voiceprint_result(
        self, device_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Store voiceprint identification result in the device shadow.

        This is called after a successful voiceprint identification during
        dialogue processing. The result includes speaker identity and confidence.
        """
        with self._lock:
            shadow = self._shadow(device_id)
            shadow.voiceprint_result = deepcopy(result)
            shadow.updated_at = _now_iso()
            return shadow.to_dict()

    def validate_voiceprint_sample(self, message: dict[str, Any]) -> dict[str, Any]:
        device_id = str(message["device_id"])
        voiceprint_id = str(message.get("voiceprint_id", ""))
        sample_index = message.get("sample_index", 0)
        audio_data = message.get("audio_data")
        format = message.get("format", "raw_pcm")
        member_id = message.get("member_id")

        if not device_id:
            raise ValueError("device_id is required")
        if not voiceprint_id:
            raise ValueError("voiceprint_id is required")
        if not isinstance(sample_index, int) or sample_index < 0:
            raise ValueError("sample_index must be a non-negative integer")
        if not audio_data or not isinstance(audio_data, str):
            raise ValueError("audio_data must be a non-empty string")
        if format not in ("raw_pcm", "wav", "opus", "g711", "pcm"):
            raise ValueError("format must be one of raw_pcm, wav, opus, g711, or pcm")

        return {
            "device_id": device_id,
            "voiceprint_id": voiceprint_id,
            "sample_index": sample_index,
            "audio_data": audio_data.strip(),
            "format": format,
            "member_id": member_id,
        }

    def snapshot(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            shadow = self._shadows.get(device_id)
            return shadow.to_dict() if shadow else None

    def delta_for_hello(self, device_id: str) -> dict[str, Any]:
        with self._lock:
            shadow = self._shadows.get(device_id)
            if shadow is None:
                return {"shadow": {"known": False, "profile_id": "", "desired": {}}}
            delta = {
                "shadow": {
                    "known": True,
                    "profile_id": shadow.profile_id,
                    "desired": deepcopy(shadow.desired),
                }
            }
            # Include voiceprint result if available
            if shadow.voiceprint_result:
                delta["voiceprint"] = deepcopy(shadow.voiceprint_result)
            return delta

    def _shadow(self, device_id: str) -> DeviceShadow:
        if device_id not in self._shadows:
            self._shadows[device_id] = DeviceShadow(device_id=device_id)
        return self._shadows[device_id]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


shadow_store = DeviceShadowStore()
