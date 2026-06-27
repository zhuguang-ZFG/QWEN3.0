"""Structural sanity checks for deploy/prometheus/startup_alerts.yml."""

from __future__ import annotations

from pathlib import Path

import pytest

import yaml


_RULES_PATH = Path("deploy/prometheus/startup_alerts.yml")


@pytest.fixture
def rules() -> dict:
    return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))


def test_rules_file_has_groups(rules: dict):
    assert "groups" in rules
    assert len(rules["groups"]) > 0


def test_startup_group_exists(rules: dict):
    names = {g["name"] for g in rules["groups"]}
    assert "lima_startup" in names


def test_all_alerts_have_required_fields(rules: dict):
    for group in rules["groups"]:
        for rule in group["rules"]:
            assert "alert" in rule
            assert "expr" in rule
            assert "labels" in rule
            assert "annotations" in rule
            assert "severity" in rule["labels"]
            assert "summary" in rule["annotations"]


def test_expected_alerts_present(rules: dict):
    alerts: set[str] = set()
    for group in rules["groups"]:
        for rule in group["rules"]:
            alerts.add(rule["alert"])
    expected = {
        "LiMaStartupPhaseSlow",
        "LiMaStartupPhaseVerySlow",
        "LiMaStartupNotReady",
        "LiMaStartupError",
    }
    assert expected <= alerts


def test_startup_phase_slow_expr_checks_histogram_bucket():
    text = _RULES_PATH.read_text(encoding="utf-8")
    assert "lima_startup_phase_duration_ms_count" in text
    assert 'lima_startup_phase_duration_ms_bucket{le="5000.0"}' in text


def test_not_ready_expr_uses_status_gauge():
    text = _RULES_PATH.read_text(encoding="utf-8")
    assert "lima_startup_status != 1" in text


def test_error_expr_uses_status_gauge_zero():
    text = _RULES_PATH.read_text(encoding="utf-8")
    assert "lima_startup_status == 0" in text
