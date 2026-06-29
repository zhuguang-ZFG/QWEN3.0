"""AUDIT-5-O3：告警规则评估器。

周期性读取 admin 面板配置的告警规则，与后端遥测/健康指标对比，
条件满足时记录告警事件，避免规则系统是"空壳"。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_EVAL_INTERVAL_SEC = 60
_MIN_COOLDOWN_SEC = 60

_state_lock = threading.Lock()
_last_fired: dict[str, float] = {}


def _data_dir() -> Path:
    from config.db_config import get_lima_data_dir

    return Path(get_lima_data_dir()) if get_lima_data_dir() else Path("data")


def _alert_log_path() -> Path:
    return _data_dir() / "alert_log.jsonl"


def _load_rules() -> list[dict[str, Any]]:
    try:
        from routes.admin_extra_alerts import iter_enabled_rules

        return iter_enabled_rules()
    except ImportError:
        return []


def _collect_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    try:
        from observability.backend_telemetry import backend_telemetry_summary

        telemetry = backend_telemetry_summary(limit=20)
        metrics["error_rate"] = telemetry.get("error_rate", 0.0)
        metrics["success_rate"] = telemetry.get("success_rate", 0.0)
        metrics["failed_recent"] = telemetry.get("failed_recent", 0)
        metrics["slow_recent"] = telemetry.get("slow_recent", 0)
        latency = telemetry.get("latency") or {}
        metrics["latency_p95"] = latency.get("p95", 0)
        metrics["latency_p99"] = latency.get("p99", 0)
    except Exception as exc:
        _log.debug("alert evaluator backend telemetry unavailable: %s", exc)

    try:
        from routes.ops_metrics.collectors import _collect_health

        _health_map, dead, degraded = _collect_health()
        metrics["dead_backends"] = len(dead)
        metrics["degraded_backends"] = len(degraded)
    except Exception as exc:
        _log.debug("alert evaluator health collection unavailable: %s", exc)

    return metrics


def _get_value(metrics: dict[str, Any], metric: str) -> float:
    value = metrics.get(metric)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _condition_met(value: float, condition: str, threshold: float) -> bool:
    if condition == "gt":
        return value > threshold
    if condition == "gte":
        return value >= threshold
    if condition == "lt":
        return value < threshold
    if condition == "lte":
        return value <= threshold
    if condition in ("eq", "equals"):
        return abs(value - threshold) < 1e-9
    return False


def _record_alert(rule: dict[str, Any], value: float, metrics: dict[str, Any]) -> None:
    path = _alert_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": time.time(),
        "rule_id": rule.get("rule_id", ""),
        "name": rule.get("name", ""),
        "metric": rule.get("metric", ""),
        "condition": rule.get("condition", ""),
        "threshold": rule.get("threshold", 0.0),
        "value": value,
        "metrics_snapshot": metrics,
    }
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n")
    except Exception as exc:
        _log.warning("failed to write alert log: %s", type(exc).__name__)
    _log.warning(
        "ALERT fired: %s (%s %s %s) value=%s",
        rule.get("name"),
        rule.get("metric"),
        rule.get("condition"),
        rule.get("threshold"),
        value,
    )


def evaluate_rule(rule: dict[str, Any], metrics: dict[str, Any]) -> tuple[bool, float]:
    metric = rule.get("metric", "error_rate")
    value = _get_value(metrics, metric)
    threshold = float(rule.get("threshold", 0.5))
    condition = rule.get("condition", "gt")
    return _condition_met(value, condition, threshold), value


def evaluate_all() -> list[dict[str, Any]]:
    """Evaluate all enabled rules once and return fired alerts."""
    rules = _load_rules()
    if not rules:
        return []
    metrics = _collect_metrics()
    now = time.time()
    fired: list[dict[str, Any]] = []
    with _state_lock:
        for rule in rules:
            rule_id = rule.get("rule_id", "")
            matched, value = evaluate_rule(rule, metrics)
            if not matched:
                continue
            last = _last_fired.get(rule_id, 0)
            cooldown = max(_MIN_COOLDOWN_SEC, int(rule.get("window_sec", 300)))
            if now - last < cooldown:
                continue
            _last_fired[rule_id] = now
            _record_alert(rule, value, metrics)
            fired.append({"rule": rule, "value": value})
    return fired


def _evaluation_loop() -> None:
    while True:
        try:
            evaluate_all()
        except Exception as exc:
            _log.warning("alert evaluator loop error: %s", type(exc).__name__)
        time.sleep(_EVAL_INTERVAL_SEC)


_evaluator_thread: threading.Thread | None = None


def start_alert_evaluator() -> None:
    """Start the daemon evaluator thread (idempotent)."""
    global _evaluator_thread
    if _evaluator_thread is not None and _evaluator_thread.is_alive():
        return
    _evaluator_thread = threading.Thread(target=_evaluation_loop, name="alert-evaluator", daemon=True)
    _evaluator_thread.start()
    _log.info("Alert evaluator started")


def stop_alert_evaluator() -> None:
    global _evaluator_thread
    if _evaluator_thread is not None and _evaluator_thread.is_alive():
        # 后台线程无法干净中断，仅置空引用；下次启动会重新创建。
        _evaluator_thread = None
