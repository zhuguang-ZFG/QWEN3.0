"""Tests for config.node_role role and capability switches."""

from __future__ import annotations

import importlib
import os

import pytest

import config.node_role as node_role
import server_lifespan_phases as phases
from router_v3.select import select_backends


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove role-related env vars before each test."""
    for name in (
        "LIMA_NODE_ROLE",
        "LIMA_SESSION_MEMORY_ENABLED",
        "LIMA_DEVICE_GATEWAY_ENABLED",
        "LIMA_MQTT_CLIENT_ENABLED",
        "LIMA_CONTEXT_RETRIEVAL_ENABLED",
        "LIMA_PROMETHEUS_ENABLED",
        "LIMA_ALERT_EVALUATOR_ENABLED",
        "LIMA_STRUCTURED_LOGGING_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(node_role)


def test_default_role_is_primary():
    assert node_role.node_role() == "primary"
    assert node_role.is_primary() is True
    assert node_role.is_free_backend_only() is False


def test_free_backend_only_role():
    os.environ["LIMA_NODE_ROLE"] = "free_backend_only"
    importlib.reload(node_role)
    assert node_role.node_role() == "free_backend_only"
    assert node_role.is_primary() is False
    assert node_role.is_free_backend_only() is True


def test_invalid_role_falls_back_to_primary():
    os.environ["LIMA_NODE_ROLE"] = "unknown"
    importlib.reload(node_role)
    assert node_role.node_role() == "primary"


@pytest.mark.parametrize(
    ("name", "getter"),
    [
        ("LIMA_SESSION_MEMORY_ENABLED", node_role.session_memory_enabled),
        ("LIMA_DEVICE_GATEWAY_ENABLED", node_role.device_gateway_enabled),
        ("LIMA_MQTT_CLIENT_ENABLED", node_role.mqtt_enabled),
        ("LIMA_CONTEXT_RETRIEVAL_ENABLED", node_role.context_retrieval_enabled),
        ("LIMA_PROMETHEUS_ENABLED", node_role.prometheus_enabled),
        ("LIMA_ALERT_EVALUATOR_ENABLED", node_role.alert_evaluator_enabled),
        ("LIMA_STRUCTURED_LOGGING_ENABLED", node_role.structured_logging_enabled),
    ],
)
def test_capability_defaults_to_enabled(name, getter):
    assert getter() is True


@pytest.mark.parametrize(
    "value",
    ["0", "false", "no", "off"],
)
def test_capabilities_can_be_disabled(value):
    os.environ["LIMA_SESSION_MEMORY_ENABLED"] = value
    os.environ["LIMA_DEVICE_GATEWAY_ENABLED"] = value
    os.environ["LIMA_MQTT_CLIENT_ENABLED"] = value
    os.environ["LIMA_CONTEXT_RETRIEVAL_ENABLED"] = value
    os.environ["LIMA_PROMETHEUS_ENABLED"] = value
    os.environ["LIMA_ALERT_EVALUATOR_ENABLED"] = value
    os.environ["LIMA_STRUCTURED_LOGGING_ENABLED"] = value
    importlib.reload(node_role)

    assert node_role.session_memory_enabled() is False
    assert node_role.device_gateway_enabled() is False
    assert node_role.mqtt_enabled() is False
    assert node_role.context_retrieval_enabled() is False
    assert node_role.prometheus_enabled() is False
    assert node_role.alert_evaluator_enabled() is False
    assert node_role.structured_logging_enabled() is False


@pytest.mark.asyncio
async def test_session_memory_daemon_skipped_when_disabled(monkeypatch, caplog):
    os.environ["LIMA_SESSION_MEMORY_ENABLED"] = "0"
    importlib.reload(node_role)

    started = []
    monkeypatch.setattr(
        phases,
        "session_memory_enabled",
        lambda: False,
    )

    with caplog.at_level("INFO", logger="server_lifespan_phases"):
        await phases.start_session_memory_daemon()

    assert "LIMA_SESSION_MEMORY_ENABLED=0; skipping session memory daemon" in caplog.text


@pytest.mark.asyncio
async def test_device_gateway_skipped_when_disabled(monkeypatch, caplog):
    monkeypatch.setattr(phases, "device_gateway_enabled", lambda: False)

    with caplog.at_level("INFO", logger="server_lifespan_phases"):
        await phases.start_device_gateway_runtime()

    assert "LIMA_DEVICE_GATEWAY_ENABLED=0; skipping device gateway runtime" in caplog.text


@pytest.mark.asyncio
async def test_mqtt_skipped_when_disabled(monkeypatch, caplog):
    monkeypatch.setattr(phases, "mqtt_enabled", lambda: False)

    with caplog.at_level("INFO", logger="server_lifespan_phases"):
        await phases.start_mqtt_client()

    assert "LIMA_MQTT_CLIENT_ENABLED=0; skipping MQTT client" in caplog.text


def test_select_backends_filters_to_cloud_free_on_auxiliary_node(monkeypatch):
    import router_v3.select as select_mod

    monkeypatch.setattr(select_mod, "is_free_backend_only", lambda: True)
    monkeypatch.setattr(select_mod.runtime_topology, "filter_backends", lambda names: list(names))

    # All backends are healthy; ddg_gpt4o_mini and google_flash are in chat floor.
    health_map = {b: "healthy" for b in ["scnet_ds_flash", "google_flash", "ddg_gpt4o_mini", "kimi"]}

    result = select_backends("chat", health_map)

    assert "scnet_ds_flash" not in result
    assert "kimi" not in result
    assert "google_flash" in result
    assert "ddg_gpt4o_mini" in result


def test_select_backends_primary_node_keeps_all_healthy_backends(monkeypatch):
    import router_v3.select as select_mod

    monkeypatch.setattr(select_mod, "is_free_backend_only", lambda: False)
    monkeypatch.setattr(select_mod.runtime_topology, "filter_backends", lambda names: list(names))

    health_map = {b: "healthy" for b in ["scnet_ds_flash", "google_flash", "ddg_gpt4o_mini"]}

    result = select_backends("chat", health_map)

    assert "scnet_ds_flash" in result
