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
import logging
from typing import Optional

from config.settings import DEVICE
from device_gateway.mqtt_handlers import (
    _drain_downlink_queues,
    _handle_mqtt_message,
)

_log = logging.getLogger(__name__)

# In-memory registry of MQTT-connected devices: device_id -> asyncio.Queue
_mqtt_devices: dict[str, asyncio.Queue[dict]] = {}
# Reference to the running event loop, set during start_mqtt_client()
_main_loop: Optional[asyncio.AbstractEventLoop] = None
# Strong reference to the MQTT message loop task so it is not GC'd.
_mqtt_loop_task: Optional[asyncio.Task] = None


def get_broker_config() -> dict:
    return {
        "broker": DEVICE.mqtt_broker,
        "port": DEVICE.mqtt_port,
        "client_id": DEVICE.mqtt_client_id,
    }


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
    if not DEVICE.mqtt_enabled:
        _log.debug("MQTT device transport disabled")
        return

    _log.info(
        "Starting MQTT device transport: %s:%s as %s",
        DEVICE.mqtt_broker,
        DEVICE.mqtt_port,
        DEVICE.mqtt_client_id,
    )

    global _main_loop, _mqtt_loop_task
    _main_loop = asyncio.get_running_loop()

    # Start background task for MQTT message loop and keep a strong reference.
    _mqtt_loop_task = asyncio.create_task(_mqtt_message_loop())


async def stop_mqtt_client() -> None:
    """Stop the MQTT client daemon."""
    if not DEVICE.mqtt_enabled:
        return
    global _mqtt_loop_task
    if _mqtt_loop_task is not None and not _mqtt_loop_task.done():
        _mqtt_loop_task.cancel()
        try:
            await _mqtt_loop_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.warning("MQTT message loop task cancelled with error: %s", exc, exc_info=True)
        finally:
            _mqtt_loop_task = None
    _mqtt_devices.clear()
    _log.info("MQTT device transport stopped")


def _create_mqtt_client(
    mqtt,
    _json,
    message_queue: asyncio.Queue[tuple[str, str, dict]],
    server_sub_filter: str,
    client_id: str,
    lwt_offline: str,
    will_topic: str,
):
    """Create and configure a paho MQTT client with asyncio bridging callbacks."""

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            _log.info("MQTT connected to %s:%s", DEVICE.mqtt_broker, DEVICE.mqtt_port)
            client.subscribe(server_sub_filter)
        else:
            _log.warning("MQTT connect failed: rc=%s", reason_code)

    def on_connect_fail(client, userdata, exc=None):
        _log.warning("MQTT connect failed asynchronously: %s", exc)

    def on_message(client, userdata, msg):
        try:
            payload = _json.loads(msg.payload.decode("utf-8", errors="replace"))
            message_queue.put_nowait((msg.topic, "uplink", payload))
        except Exception as exc:
            _log.warning("MQTT message parse failed topic=%s: %s", msg.topic, exc)

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        _log.info("MQTT disconnected: rc=%s", reason_code)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.will_set(will_topic, lwt_offline, qos=0, retain=True)
    return client


async def _run_mqtt_message_pump(
    client,
    message_queue: asyncio.Queue[tuple[str, str, dict]],
    _json,
    _time_mod,
) -> None:
    """Dequeue MQTT uplink messages and drain downlink queues."""
    while True:
        try:
            topic, direction, payload = await asyncio.wait_for(message_queue.get(), timeout=1.0)
            _handle_mqtt_message(client, topic, payload, _json, _time_mod)
        except asyncio.TimeoutError:
            pass
        _drain_downlink_queues(client, _json)


def _shutdown_mqtt_client(client) -> None:
    """Stop the MQTT network loop and disconnect cleanly."""
    client.loop_stop()
    client.disconnect()
    _log.info("MQTT transport stopped")


async def _mqtt_message_loop() -> None:
    """Main MQTT message processing loop using paho-mqtt.

    Requires: pip install paho-mqtt
    The MQTT client runs paho's network loop in a background thread
    and bridges incoming messages to asyncio via queues.
    """
    try:
        import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
        import json as _json
        import time as _time_mod
    except ImportError:
        _log.info("paho-mqtt not installed; MQTT transport remains in stub mode")
        _log.info("Install: pip install paho-mqtt")
        while True:
            await asyncio.sleep(3600)
        return  # unreachable

    from device_gateway.mqtt_topics import (
        LWT_OFFLINE,
        SERVER_SUB_FILTER,
        device_status_topic,
    )

    message_queue: asyncio.Queue[tuple[str, str, dict]] = asyncio.Queue()
    client = _create_mqtt_client(
        mqtt,
        _json,
        message_queue,
        SERVER_SUB_FILTER,
        DEVICE.mqtt_client_id,
        LWT_OFFLINE,
        device_status_topic(DEVICE.mqtt_client_id),
    )

    # Use connect_async + loop_start to avoid blocking the asyncio event loop
    # while the TCP/TLS handshake proceeds in paho's background thread.
    client.loop_start()
    try:
        client.connect_async(DEVICE.mqtt_broker, DEVICE.mqtt_port, keepalive=60)
    except Exception as exc:
        _log.error("MQTT async connect schedule failed: %s", exc)
        client.loop_stop()
        return

    try:
        await _run_mqtt_message_pump(client, message_queue, _json, _time_mod)
    finally:
        _shutdown_mqtt_client(client)
