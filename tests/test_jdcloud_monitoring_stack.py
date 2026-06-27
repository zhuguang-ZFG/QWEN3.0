"""Sanity checks for deploy/jdcloud/deploy_monitoring_stack.sh content."""

from __future__ import annotations

from pathlib import Path

import pytest


SCRIPT_PATH = Path("deploy/jdcloud/deploy_monitoring_stack.sh")
UPDATE_SCRIPT_PATH = Path("deploy/jdcloud/update_startup_alerts.sh")


def _script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_deploy_script_exists():
    assert SCRIPT_PATH.exists()


def test_deploy_script_creates_rules_directory():
    text = _script_text()
    assert "mkdir -p prometheus/rules" in text


def test_deploy_script_writes_startup_alerts():
    text = _script_text()
    assert "LiMaStartupPhaseSlow" in text
    assert "LiMaStartupPhaseVerySlow" in text
    assert "LiMaStartupNotReady" in text
    assert "LiMaStartupError" in text


def test_deploy_script_prometheus_yml_has_rule_files():
    text = _script_text()
    assert "rule_files:" in text
    assert "/etc/prometheus/rules/*.yml" in text


def test_deploy_script_prometheus_yml_scrapes_lima_metrics():
    text = _script_text()
    assert "metrics_path: /v1/ops/metrics/prometheus" in text
    assert "LIMA_METRICS_API_KEY" in text


def test_deploy_script_compose_mounts_rules():
    text = _script_text()
    assert "./prometheus/rules:/etc/prometheus/rules:ro" in text


def test_update_script_exists():
    assert UPDATE_SCRIPT_PATH.exists()


def test_update_script_writes_rules_and_reloads():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "LiMaStartupNotReady" in text
    assert "startup_alerts.yml" in text
    assert "http://localhost:9090/-/reload" in text
