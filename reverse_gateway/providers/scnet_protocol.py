"""SCNet reverse protocol template loading and redaction."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROTOCOL_PATH = "/opt/lima-router/reverse_gateway_state/scnet_protocol.json"
SECRET_HEADER_NAMES = {
    "authorization",
    "cookie",
    "x-api-key",
    "x-csrf-token",
    "x-xsrf-token",
    "set-cookie",
}
REDACTED = "<redacted>"


@dataclass(frozen=True)
class ProtocolTemplate:
    endpoint: str
    method: str
    headers: dict[str, str]
    payload_template: dict[str, Any]
    stream: bool = False

    def redacted(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "headers": redact_headers(self.headers),
            "payload_template": self.payload_template,
            "stream": self.stream,
        }


def protocol_path() -> Path:
    return Path(os.environ.get("SCNET_REVERSE_PROTOCOL_PATH", DEFAULT_PROTOCOL_PATH))


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        name: REDACTED if name.lower() in SECRET_HEADER_NAMES else value
        for name, value in headers.items()
    }


def validate_template(raw: dict[str, Any]) -> ProtocolTemplate:
    endpoint = str(raw.get("endpoint") or "").strip()
    if not endpoint.startswith(("https://", "http://")):
        raise ValueError("protocol endpoint must be http(s)")
    method = str(raw.get("method") or "POST").upper()
    if method not in {"POST"}:
        raise ValueError("only POST protocol templates are supported")
    headers = raw.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError("protocol headers must be an object")
    payload = raw.get("payload_template") or {}
    if not isinstance(payload, dict):
        raise ValueError("protocol payload_template must be an object")
    return ProtocolTemplate(
        endpoint=endpoint,
        method=method,
        headers={str(k): str(v) for k, v in headers.items()},
        payload_template=payload,
        stream=bool(raw.get("stream", False)),
    )


def load_template(path: Path | None = None) -> ProtocolTemplate | None:
    selected = path or protocol_path()
    if not selected.is_file():
        return None
    raw = json.loads(selected.read_text(encoding="utf-8-sig"))
    return validate_template(raw)


def write_redacted_capture(raw: dict[str, Any], path: Path) -> ProtocolTemplate:
    template = validate_template(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(template.redacted(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return template
