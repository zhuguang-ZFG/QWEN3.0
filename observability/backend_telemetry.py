"""Sanitized backend attempt telemetry for operator diagnostics."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

MAX_RECENT = 500
_log = logging.getLogger(__name__)


def _data_dir() -> Path:
    return Path(os.environ.get("LIMA_DATA_DIR", "data"))


def _telemetry_path() -> Path:
    return _data_dir() / "backend_telemetry.jsonl"


def _short(value: Any, limit: int = 80) -> str:
    text = str(value or "")
    if not text:
        return ""
    try:
        from session_memory.redact import sanitize_for_display

        text = sanitize_for_display(text)
    except ImportError:
        lowered = text.lower()
        if any(token in lowered for token in (
            "bearer ", "sk-", "api_key", "token", "password", "secret",
        )):
            text = "[REDACTED]"
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


def _status(value: Any) -> int:
    code = _int(value, 0)
    return code if code > 0 else 0


def classify_error(
    *,
    status_code: Any = None,
    error: Any = None,
    response_empty: bool = False,
    success: bool = False,
) -> str:
    if success:
        return ""
    if response_empty:
        return "empty_response"

    code = _status(status_code)
    if code in (401, 403):
        return "auth"
    if code == 402:
        return "quota"
    if code in (408, 504):
        return "timeout"
    if code == 429:
        return "rate_limit"
    if code >= 500:
        return "provider_5xx"
    if code >= 400:
        return "admission_blocked"

    text = str(error or "").lower()
    if not text:
        return "unknown"
    if any(token in text for token in ("timeout", "timed out", "abort", "readtimeout")):
        return "timeout"
    if any(token in text for token in ("insufficient balance", "quota", "credit", "billing", "402")):
        return "quota"
    if any(token in text for token in ("429", "rate limit", "rate_limit")):
        return "rate_limit"
    if any(token in text for token in ("401", "403", "forbidden", "unauthorized", "auth")):
        return "auth"
    if any(token in text for token in ("blocked", "admission", "moderation", "policy")):
        return "admission_blocked"
    if any(token in text for token in ("empty", "no content", "no_content")):
        return "empty_response"
    if any(token in text for token in ("5xx", "internal", "upstream", "provider")):
        return "provider_5xx"
    if any(token in text for token in ("network", "connect", "reset", "dns")):
        return "network"
    return "unknown"


def record_backend_attempt(
    *,
    backend: str,
    scenario: str = "",
    request_type: str = "",
    success: bool,
    latency_ms: float = 0.0,
    tools_requested: bool = False,
    status_code: Any = None,
    error: Any = None,
    response_empty: bool = False,
    phase: str = "route",
    attempt: str = "serial",
    model: str = "",
) -> bool:
    record = {
        "ts": int(time.time()),
        "backend": _short(backend),
        "scenario": _short(scenario, 40),
        "request_type": _short(request_type, 40),
        "phase": _short(phase, 40),
        "attempt": _short(attempt, 40),
        "model": _short(model, 80),
        "success": bool(success),
        "latency_ms": _int(latency_ms),
        "tools_requested": bool(tools_requested),
        "status_code": _status(status_code),
        "error_class": classify_error(
            status_code=status_code,
            error=error,
            response_empty=response_empty,
            success=success,
        ),
    }
    try:
        path = _telemetry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        return True
    except Exception as exc:
        _log.warning("failed to record backend telemetry: %s", type(exc).__name__)
        return False


def _read_recent(limit: int) -> list[dict[str, Any]]:
    path = _telemetry_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(limit, 1):]
    except Exception as exc:
        _log.warning("failed to read backend telemetry: %s", type(exc).__name__)
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


def backend_telemetry_summary(limit: int = 20, slow_ms: int = 30000) -> dict[str, Any]:
    records = _read_recent(max(limit, MAX_RECENT))
    total = len(records)
    failures = sum(1 for item in records if not item.get("success", False))
    slow = sum(1 for item in records if _int(item.get("latency_ms", 0)) >= slow_ms)
    error_classes: dict[str, int] = {}
    per_backend: dict[str, dict[str, Any]] = {}

    for item in records:
        backend = _short(item.get("backend", "unknown")) or "unknown"
        latency = _int(item.get("latency_ms", 0))
        error_class = _short(item.get("error_class", ""), 40)
        success = bool(item.get("success", False))
        stats = per_backend.setdefault(
            backend,
            {
                "attempts": 0,
                "success": 0,
                "failures": 0,
                "total_latency_ms": 0,
                "max_latency_ms": 0,
                "slow": 0,
                "error_classes": {},
            },
        )
        stats["attempts"] += 1
        stats["success"] += int(success)
        stats["failures"] += int(not success)
        stats["total_latency_ms"] += latency
        stats["max_latency_ms"] = max(stats["max_latency_ms"], latency)
        stats["slow"] += int(latency >= slow_ms)
        if error_class:
            error_classes[error_class] = error_classes.get(error_class, 0) + 1
            nested = stats["error_classes"]
            nested[error_class] = nested.get(error_class, 0) + 1

    by_backend: dict[str, dict[str, Any]] = {}
    ranked = sorted(
        per_backend.items(),
        key=lambda pair: (-pair[1]["attempts"], pair[0]),
    )[:10]
    for backend, stats in ranked:
        attempts = max(int(stats["attempts"]), 1)
        by_backend[backend] = {
            "attempts": int(stats["attempts"]),
            "success": int(stats["success"]),
            "failures": int(stats["failures"]),
            "avg_latency_ms": int(stats["total_latency_ms"] / attempts),
            "max_latency_ms": int(stats["max_latency_ms"]),
            "slow": int(stats["slow"]),
            "error_classes": dict(stats["error_classes"]),
        }

    return {
        "total_recent": total,
        "failed_recent": failures,
        "slow_recent": slow,
        "error_classes": error_classes,
        "by_backend": by_backend,
        "recent": records[-limit:],
    }
