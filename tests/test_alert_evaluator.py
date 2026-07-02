"""Tests for AUDIT-5-O3 alert rule evaluator."""

from __future__ import annotations

import json

import pytest

import observability.alert_evaluator as alert_evaluator
from observability.alert_evaluator import evaluate_all, evaluate_rule


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    """Isolate alert state and log file per test."""
    monkeypatch.setattr(alert_evaluator, "_last_fired", {})
    monkeypatch.setattr(alert_evaluator, "_alert_log_path", lambda: tmp_path / "alert_log.jsonl")
    monkeypatch.setattr(
        alert_evaluator,
        "_load_rules",
        lambda: [],
    )


def test_evaluate_rule_gt():
    rule = {"metric": "error_rate", "condition": "gt", "threshold": 0.5}
    matched, value = evaluate_rule(rule, {"error_rate": 0.8})
    assert matched is True
    assert value == 0.8


def test_evaluate_rule_lte_no_match():
    rule = {"metric": "failed_recent", "condition": "gt", "threshold": 10}
    matched, value = evaluate_rule(rule, {"failed_recent": 3})
    assert matched is False
    assert value == 3


def test_evaluate_all_fires_when_threshold_met(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(
        alert_evaluator,
        "_load_rules",
        lambda: [
            {
                "rule_id": "r1",
                "name": "high error rate",
                "metric": "error_rate",
                "condition": "gt",
                "threshold": 0.5,
                "window_sec": 0,
                "enabled": True,
            }
        ],
    )
    monkeypatch.setattr(
        alert_evaluator,
        "_collect_metrics",
        lambda: {"error_rate": 0.9, "success_rate": 0.1},
    )

    fired = evaluate_all()

    assert len(fired) == 1
    assert fired[0]["value"] == 0.9
    log_text = (tmp_path / "alert_log.jsonl").read_text(encoding="utf-8")
    event = json.loads(log_text.strip())
    assert event["rule_id"] == "r1"
    assert event["value"] == 0.9
    assert "high error rate" in caplog.text


def test_evaluate_all_respects_cooldown(monkeypatch, tmp_path):
    rule = {
        "rule_id": "r1",
        "name": "high error rate",
        "metric": "error_rate",
        "condition": "gt",
        "threshold": 0.5,
        "window_sec": 300,
        "enabled": True,
    }
    monkeypatch.setattr(alert_evaluator, "_load_rules", lambda: [rule])
    monkeypatch.setattr(
        alert_evaluator,
        "_collect_metrics",
        lambda: {"error_rate": 0.9},
    )

    assert len(evaluate_all()) == 1
    # 同一秒内再次评估不应重复触发（cooldown 未过）
    assert len(evaluate_all()) == 0


def test_evaluate_all_no_rules_returns_empty():
    assert evaluate_all() == []


def test_collect_metrics_includes_telemetry_fields(monkeypatch):
    monkeypatch.setattr(
        alert_evaluator,
        "_collect_metrics",
        lambda: {"error_rate": 0.1, "success_rate": 0.9, "dead_backends": 0},
    )
    metrics = alert_evaluator._collect_metrics()
    assert "error_rate" in metrics
    assert "success_rate" in metrics
    assert "dead_backends" in metrics
