"""Tests for MQTT device transport boundary enforcement."""

from __future__ import annotations

import json


class _FakeClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))


def test_mqtt_hello_requires_valid_device_token(monkeypatch):
    from device_gateway import mqtt_client

    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=good-token")
    mqtt_client.unregister_mqtt_device("dev-1")

    client = _FakeClient()
    mqtt_client._handle_mqtt_message(client, "lima/dev-1/uplink", {"type": "hello"}, json, __import__("time"))

    assert "dev-1" not in mqtt_client.get_mqtt_device_ids()
    assert client.published == []


def test_mqtt_rejects_topic_payload_device_mismatch(monkeypatch):
    from device_gateway import mqtt_client

    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=good-token")
    mqtt_client.unregister_mqtt_device("dev-1")

    client = _FakeClient()
    mqtt_client._handle_mqtt_message(
        client,
        "lima/dev-1/uplink",
        {
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": "other-dev",
            "token": "good-token",
            "capabilities": [],
        },
        json,
        __import__("time"),
    )

    assert "dev-1" not in mqtt_client.get_mqtt_device_ids()
    assert client.published == []


def test_mqtt_accepts_valid_hello(monkeypatch):
    from device_gateway import mqtt_client

    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=good-token")
    mqtt_client.unregister_mqtt_device("dev-1")

    client = _FakeClient()
    mqtt_client._handle_mqtt_message(
        client,
        "lima/dev-1/uplink",
        {
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": "dev-1",
            "token": "good-token",
            "capabilities": [],
        },
        json,
        __import__("time"),
    )

    assert "dev-1" in mqtt_client.get_mqtt_device_ids()
    assert client.published


def test_mqtt_rejects_motion_event_without_authenticated_session(monkeypatch):
    from device_gateway import mqtt_client

    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=good-token")
    mqtt_client.unregister_mqtt_device("dev-1")

    client = _FakeClient()
    mqtt_client._handle_mqtt_message(
        client,
        "lima/dev-1/uplink",
        {
            "type": "motion_event",
            "device_id": "dev-1",
            "task_id": "task-1",
            "phase": "completed",
        },
        json,
        __import__("time"),
    )

    assert client.published == []


def test_mqtt_rejects_heartbeat_with_wrong_token_after_hello(monkeypatch):
    from device_gateway import mqtt_client

    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=good-token")
    mqtt_client.unregister_mqtt_device("dev-1")

    client = _FakeClient()
    mqtt_client._handle_mqtt_message(
        client,
        "lima/dev-1/uplink",
        {
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": "dev-1",
            "token": "good-token",
            "capabilities": [],
        },
        json,
        __import__("time"),
    )
    client.published.clear()

    mqtt_client._handle_mqtt_message(
        client,
        "lima/dev-1/uplink",
        {
            "type": "heartbeat",
            "device_id": "dev-1",
            "uptime_ms": 1,
            "token": "bad-token",
        },
        json,
        __import__("time"),
    )

    assert client.published == []
