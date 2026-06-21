"""Device profile field parsing and safe SQL assignment builders."""

from __future__ import annotations

import json
from typing import Any

from device_logic.errors import DeviceLogicError

ALLOWED_DEVICE_COLUMNS = frozenset({"model", "firmware_ver", "hardware_ver", "metadata"})


def _json_metadata(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, str):
        return value
    raise DeviceLogicError(400, "metadata must be an object or string", 400)


def parse_device_updates(body: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for body_name, column_name in (
        ("model", "model"),
        ("firmwareVer", "firmware_ver"),
        ("firmware_ver", "firmware_ver"),
        ("hardwareVer", "hardware_ver"),
        ("hardware_ver", "hardware_ver"),
    ):
        value = body.get(body_name)
        if isinstance(value, str) and value.strip():
            updates[column_name] = value.strip()
    if "metadata" in body:
        updates["metadata"] = _json_metadata(body["metadata"])
    if not updates:
        raise DeviceLogicError(400, "no supported device fields provided", 400)
    return updates


def sql_set_clause(updates: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    for column in updates:
        if column not in ALLOWED_DEVICE_COLUMNS:
            raise DeviceLogicError(400, f"Disallowed column: {column!r}", 400)
    assignments = ", ".join(f"{column}=?" for column in updates)
    return assignments, tuple(updates.values())
