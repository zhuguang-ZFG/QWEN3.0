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

_BACKEND_STATS_TEMPLATE = {
    "attempts": 0,
    "success": 0,
    "failures": 0,
    "total_latency_ms": 0,
    "max_latency_ms": 0,
    "slow": 0,
    "error_classes": {},
}


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
        if any(
            token in lowered
            for token in (
                "bearer ",
                "sk-",
                "api_key",
                "token",
                "password",
                "secret",
            )
        ):
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
    from observability.jsonl_store import append_jsonl_record

    return append_jsonl_record(
        _telemetry_path(),
        record,
        keep_lines=MAX_RECENT,
        logger=_log,
    )


def _read_recent(limit: int) -> list[dict[str, Any]]:
    path = _telemetry_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(limit, 1) :]
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


def recent_backend_attempts(limit: int = MAX_RECENT) -> list[dict[str, Any]]:
    return _read_recent(max(limit, 1))


def _build_success_rate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    failures = sum(1 for item in records if not item.get("success", False))
    error_classes: dict[str, int] = {}
    for item in records:
        error_class = _short(item.get("error_class", ""), 40)
        if error_class:
            error_classes[error_class] = error_classes.get(error_class, 0) + 1
    success = total - failures
    return {
        "total": total,
        "success": success,
        "failures": failures,
        "success_rate": round(success / max(total, 1), 4),
        "error_rate": round(failures / max(total, 1), 4),
        "error_classes": error_classes,
    }


def _build_latency_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = sorted(_int(item.get("latency_ms", 0)) for item in records)
    if not latencies:
        return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
    n = len(latencies)

    def pct(p: float) -> int:
        if n == 1:
            return latencies[0]
        k = (p / 100) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            return latencies[f]
        return int(latencies[f] + (latencies[c] - latencies[f]) * (k - f))

    return {
        "min": latencies[0],
        "max": latencies[-1],
        "avg": int(sum(latencies) / n),
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
    }


def _build_status_breakdown(records: list[dict[str, Any]]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for item in records:
        code = _status(item.get("status_code", 0))
        if code > 0:
            key = str(code)
            breakdown[key] = breakdown.get(key, 0) + 1
    return breakdown


def backend_telemetry_summary(limit: int = 20, slow_ms: int = 30000) -> dict[str, Any]:
    records = recent_backend_attempts(max(limit, MAX_RECENT))
    success_metrics = _build_success_rate_metrics(records)
    latency_metrics = _build_latency_metrics(records)
    status_breakdown = _build_status_breakdown(records)
    slow = sum(1 for item in records if _int(item.get("latency_ms", 0)) >= slow_ms)
    per_backend: dict[str, dict[str, Any]] = {}
    for item in records:
        backend = _short(item.get("backend", "unknown")) or "unknown"
        latency = _int(item.get("latency_ms", 0))
        ok = bool(item.get("success", False))
        err = _short(item.get("error_class", ""), 40)
        stats = per_backend.setdefault(backend, _BACKEND_STATS_TEMPLATE.copy())
        stats["attempts"] += 1
        stats["success"] += int(ok)
        stats["failures"] += int(not ok)
        stats["total_latency_ms"] += latency
        stats["max_latency_ms"] = max(stats["max_latency_ms"], latency)
        stats["slow"] += int(latency >= slow_ms)
        if err:
            stats["error_classes"][err] = stats["error_classes"].get(err, 0) + 1
    by_backend: dict[str, dict[str, Any]] = {}
    ranked = sorted(per_backend.items(), key=lambda pair: (-pair[1]["attempts"], pair[0]))[:10]
    for backend, stats in ranked:
        attempts = max(int(stats["attempts"]), 1)
        by_backend[backend] = {k: int(stats[k]) for k in ("attempts", "success", "failures", "max_latency_ms", "slow")}
        by_backend[backend]["avg_latency_ms"] = int(stats["total_latency_ms"] / attempts)
        by_backend[backend]["error_classes"] = dict(stats["error_classes"])
    return {
        "total_recent": success_metrics["total"],
        "failed_recent": success_metrics["failures"],
        "slow_recent": slow,
        "error_classes": success_metrics["error_classes"],
        "success_rate": success_metrics["success_rate"],
        "error_rate": success_metrics["error_rate"],
        "latency": latency_metrics,
        "status_breakdown": status_breakdown,
        "by_backend": by_backend,
        "recent": records[-limit:],
    }
