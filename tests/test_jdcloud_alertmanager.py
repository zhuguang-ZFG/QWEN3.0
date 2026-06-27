"""Structural checks for deploy/jdcloud/alertmanager configuration and update script."""

from __future__ import annotations

from pathlib import Path

import pytest

import yaml


CONFIG_PATH = Path("deploy/jdcloud/alertmanager/alertmanager.yml")
UPDATE_SCRIPT_PATH = Path("deploy/jdcloud/update_alertmanager.sh")


@pytest.fixture
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_alertmanager_config_exists():
    assert CONFIG_PATH.exists()


def test_alertmanager_config_has_route(config: dict):
    assert "route" in config
    assert "receiver" in config["route"]


def test_alertmanager_config_has_critical_and_lima_router_receivers(config: dict):
    receivers = {r["name"] for r in config["receivers"]}
    assert "critical" in receivers
    assert "lima-router" in receivers


def test_alertmanager_config_uses_placeholder_webhooks():
    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert "__DINGTALK_WEBHOOK_URL__" in text
    assert "__WECHAT_WEBHOOK_URL__" in text


def test_alertmanager_config_has_inhibit_rule_for_critical_over_warning(config: dict):
    assert len(config.get("inhibit_rules", [])) > 0
    rule = config["inhibit_rules"][0]
    assert rule.get("source_match", {}).get("severity") == "critical"
    assert rule.get("target_match", {}).get("severity") == "warning"


def test_update_alertmanager_script_exists():
    assert UPDATE_SCRIPT_PATH.exists()


def test_update_script_installs_to_opt_lima_monitoring():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "/opt/lima-monitoring" in text


def test_update_script_downloads_alertmanager():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "alertmanager" in text.lower()
    assert "wget" in text or "curl" in text


def test_update_script_replaces_webhook_placeholders():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "DINGTALK_WEBHOOK_URL" in text
    assert "WECHAT_WEBHOOK_URL" in text
    assert "__DINGTALK_WEBHOOK_URL__" in text
    assert "__WECHAT_WEBHOOK_URL__" in text


def test_update_script_creates_systemd_service():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "alertmanager.service" in text
    assert "systemctl daemon-reload" in text


def test_update_script_wires_prometheus_to_alertmanager():
    text = UPDATE_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "alerting:" in text
    assert "127.0.0.1:9093" in text
