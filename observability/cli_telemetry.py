"""Sanitized LiMa Code CLI telemetry aggregation."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)
MAX_RECENT = 200


def _data_dir() -> Path:
    return Path(os.environ.get("LIMA_DATA_DIR", "data"))


def _telemetry_path() -> Path:
    return _data_dir() / "cli_telemetry.jsonl"


def _short(value: Any, limit: int = 80) -> str:
    text = str(value or "")
    return text[:limit]


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    return int(_number(value, default))


def _error_class(value: Any) -> str:
    text = str(value or "").lower()
    if not text:
        return ""
    if "timeout" in text or "abort" in text:
        return "timeout"
    if "401" in text or "403" in text or "forbidden" in text or "unauthorized" in text:
        return "auth"
    if "429" in text or "rate" in text or "quota" in text:
        return "rate_limit"
    if "5" in text[:20] or "reset" in text or "network" in text or "connect" in text:
        return "network_or_provider"
    return "provider_error"


def _model_call_summary(calls: Any) -> dict[str, Any]:
    if not isinstance(calls, list):
        calls = []
    total = len(calls)
    failed = 0
    total_latency = 0
    max_latency = 0
    error_classes: dict[str, int] = {}
    for raw in calls:
        call = raw if isinstance(raw, dict) else {}
        latency = _int(call.get("latencyMs", call.get("latency_ms", 0)))
        total_latency += latency
        max_latency = max(max_latency, latency)
        if not bool(call.get("ok", False)):
            failed += 1
            klass = _error_class(call.get("error"))
            if klass:
                error_classes[klass] = error_classes.get(klass, 0) + 1
    return {
        "total": total,
        "failed": failed,
        "total_latency_ms": total_latency,
        "max_latency_ms": max_latency,
        "error_classes": error_classes,
    }


def _tool_capability(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "requested": bool(data.get("requested", False)),
        "observed": bool(data.get("observed", False)),
        "protocol": _short(data.get("protocol", "none"), 20),
        "tool_calls": _int(data.get("toolCalls", data.get("tool_calls", 0))),
        "unsupported_reason": _short(data.get("unsupportedReason", data.get("unsupported_reason", "")), 80),
    }


def sanitize_cli_outcome(
    *,
    task_id: str,
    backend: str,
    scenario: str,
    success: bool,
    latency_ms: float,
    telemetry: dict[str, Any] | None,
) -> dict[str, Any]:
    data = telemetry or {}
    calls = _model_call_summary(data.get("modelCalls", data.get("model_calls", [])))
    return {
        "ts": int(time.time()),
        "task_id": _short(task_id, 80),
        "backend": _short(backend, 80),
        "scenario": _short(scenario, 40),
        "success": bool(success),
        "latency_ms": int(_number(latency_ms)),
        "timeout_ms": _int(data.get("timeoutMs", data.get("timeout_ms", 0))),
        "max_retries": _int(data.get("maxRetries", data.get("max_retries", 0))),
        "retry_count": _int(data.get("retryCount", data.get("retry_count", 0))),
        "model_calls": calls,
        "tool_capability": _tool_capability(data.get("toolCapability", data.get("tool_capability", {}))),
    }


def record_cli_outcome(record: dict[str, Any]) -> bool:
    path = _telemetry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        return True
    except Exception as exc:
        _log.warning("failed to record cli telemetry: %s", type(exc).__name__)
        return False


def _read_recent(limit: int) -> list[dict[str, Any]]:
    path = _telemetry_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(limit, 1):]
    except Exception as exc:
        _log.warning("failed to read cli telemetry: %s", type(exc).__name__)
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def cli_telemetry_summary(limit: int = 20) -> dict[str, Any]:
    records = _read_recent(max(limit, MAX_RECENT))
    total = len(records)
    failures = sum(1 for item in records if not item.get("success", False))
    retries = sum(_int(item.get("retry_count", 0)) for item in records)
    tool_observed = sum(1 for item in records if (item.get("tool_capability") or {}).get("observed"))
    model_failures = sum(_int((item.get("model_calls") or {}).get("failed", 0)) for item in records)
    recent = records[-limit:]
    return {
        "total_recent": total,
        "failed_recent": failures,
        "retry_count_recent": retries,
        "model_call_failures_recent": model_failures,
        "tool_capability_observed_recent": tool_observed,
        "recent": recent,
    }
