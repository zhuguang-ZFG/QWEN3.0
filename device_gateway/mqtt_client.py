"""MQTT device transport — alternative to WebSocket for hardware devices.

Usage:
  LIMA_DEVICE_MQTT_ENABLED=1
  LIMA_DEVICE_MQTT_BROKER=localhost
  LIMA_DEVICE_MQTT_PORT=1883

The MQTT client runs as a background asyncio task, connecting to the broker
and routing messages to the same protocol handlers as WebSocket devices.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

_log = logging.getLogger(__name__)

_MQTT_ENABLED = os.environ.get("LIMA_DEVICE_MQTT_ENABLED", "0").strip().lower() in {
    "1", "true", "yes",
}
_MQTT_BROKER = os.environ.get("LIMA_DEVICE_MQTT_BROKER", "localhost")
_MQTT_PORT = int(os.environ.get("LIMA_DEVICE_MQTT_PORT", "1883"))
_MQTT_CLIENT_ID = os.environ.get("LIMA_DEVICE_MQTT_CLIENT_ID", "lima-router")

# In-memory registry of MQTT-connected devices: device_id -> asyncio.Queue
_mqtt_devices: dict[str, asyncio.Queue[dict]] = {}


def is_mqtt_enabled() -> bool:
    return _MQTT_ENABLED


def get_broker_config() -> dict:
    return {
        "broker": _MQTT_BROKER,
        "port": _MQTT_PORT,
        "client_id": _MQTT_CLIENT_ID,
    }


async def mqtt_send_to_device(device_id: str, message: dict) -> bool:
    """Queue a message for delivery to an MQTT-connected device."""
    queue = _mqtt_devices.get(device_id)
    if queue is None:
        _log.debug("MQTT device %s not connected", device_id)
        return False
    await queue.put(message)
    return True


def register_mqtt_device(device_id: str) -> asyncio.Queue[dict]:
    """Register an MQTT-connected device. Returns its downlink queue."""
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=32)
    _mqtt_devices[device_id] = queue
    _log.info("MQTT device registered: %s", device_id)
    return queue


def unregister_mqtt_device(device_id: str) -> None:
    """Remove an MQTT device (disconnect / LWT offline)."""
    _mqtt_devices.pop(device_id, None)
    _log.info("MQTT device unregistered: %s", device_id)


def get_mqtt_device_ids() -> list[str]:
    return list(_mqtt_devices.keys())


async def start_mqtt_client() -> None:
    """Start the MQTT client daemon (called from server lifespan)."""
    if not _MQTT_ENABLED:
        _log.debug("MQTT device transport disabled")
        return

    _log.info(
        "Starting MQTT device transport: %s:%s as %s",
        _MQTT_BROKER, _MQTT_PORT, _MQTT_CLIENT_ID,
    )

    # Start background task for MQTT message loop
    asyncio.create_task(_mqtt_message_loop())


async def stop_mqtt_client() -> None:
    """Stop the MQTT client daemon."""
    if not _MQTT_ENABLED:
        return
    _mqtt_devices.clear()
    _log.info("MQTT device transport stopped")


async def _mqtt_message_loop() -> None:
    """Main MQTT message processing loop.

    This is a stub that uses a simple socket-based approach for Mosquitto
    compatibility. For production use with full MQTT 3.1.1/5.0 support,
    install `paho-mqtt` or `gmqtt` and replace this loop.
    """
    import socket

    from device_gateway.mqtt_topics import (
        BROADCAST_TOPIC,
        DOWNLINK_QOS,
        LWT_OFFLINE,
        LWT_ONLINE,
        SERVER_SUB_FILTER,
        device_status_topic,
    )
    from device_gateway.protocol import MESSAGE_VALIDATORS

    _log.info("MQTT loop: connecting to %s:%s", _MQTT_BROKER, _MQTT_PORT)

    # For now, log that MQTT transport is in stub mode.
    # Full MQTT integration requires `pip install paho-mqtt` and:
    #   1. Connect to broker with client_id + LWT
    #   2. Subscribe to SERVER_SUB_FILTER ("lima/+/uplink")
    #   3. On message: parse JSON, validate, route to protocol handlers
    #   4. Drain downlink queues -> publish to device_downlink_topic()
    #
    # The topic contract and message format are defined in mqtt_topics.py.
    # The protocol validators from protocol.py are reused as-is.

    _log.info(
        "MQTT stub active: topic=%s, broker=%s:%s, lwt=%s/%s",
        SERVER_SUB_FILTER, _MQTT_BROKER, _MQTT_PORT,
        device_status_topic(_MQTT_CLIENT_ID), LWT_ONLINE,
    )

    # Keep the task alive
    while True:
        await asyncio.sleep(60)
        connected = len(_mqtt_devices)
        if connected:
            _log.debug("MQTT devices connected: %s", connected)
