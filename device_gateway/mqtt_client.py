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
import os

_log = logging.getLogger(__name__)

_MQTT_ENABLED = os.environ.get("LIMA_DEVICE_MQTT_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
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


def _handle_mqtt_message(client, topic: str, payload: dict, _json, _time_mod) -> None:
    """Process a single MQTT uplink message (hello / heartbeat / motion_event)."""
    from device_gateway.auth import validate_device_token
    from device_gateway.protocol import ProtocolError, validate_uplink

    parts = topic.split("/")
    device_id = parts[1] if len(parts) > 1 else ""
    try:
        message = validate_uplink(payload)
    except ProtocolError as exc:
        _log.warning("MQTT protocol error topic=%s code=%s", topic, exc.code)
        return
    if not device_id or message.get("device_id") != device_id:
        _log.warning("MQTT device mismatch topic=%s payload_device=%s", topic, message.get("device_id", ""))
        return
    token = _extract_mqtt_token(payload)
    if not validate_device_token(device_id, token):
        _log.warning("MQTT unauthorized device=%s type=%s", device_id, message.get("type", ""))
        return
    msg_type = message["type"]

    if msg_type == "hello" and device_id:
        register_mqtt_device(device_id)
        from device_gateway.mqtt_topics import device_downlink_topic

        ack = {
            "type": "hello_ack",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "server_time": int(_time_mod.time()),
        }
        client.publish(device_downlink_topic(device_id), _json.dumps(ack), qos=1)

    if msg_type == "heartbeat" and device_id:
        if device_id not in _mqtt_devices:
            _log.warning("MQTT heartbeat before hello device=%s", device_id)
            return
        from device_gateway.mqtt_topics import device_downlink_topic

        ack = {"type": "heartbeat_ack", "device_id": device_id, "server_time": int(_time_mod.time())}
        client.publish(device_downlink_topic(device_id), _json.dumps(ack), qos=0)

    if msg_type == "motion_event" and device_id:
        if device_id not in _mqtt_devices:
            _log.warning("MQTT motion_event before hello device=%s", device_id)
            return
        try:
            from routes.device_gateway_ws_handlers import handle_motion_event

            asyncio.get_event_loop().create_task(handle_motion_event(device_id, message, None))
        except Exception:
            _log.debug("motion event forward failed", exc_info=True)


def _extract_mqtt_token(payload: dict) -> str:
    value = str(payload.get("token") or payload.get("authorization") or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _drain_downlink_queues(client, _json) -> None:
    """Drain per-device downlink queues and publish messages."""
    from device_gateway.mqtt_topics import device_downlink_topic

    for did, q in list(_mqtt_devices.items()):
        try:
            while True:
                msg = q.get_nowait()
                client.publish(device_downlink_topic(did), _json.dumps(msg), qos=1)
        except asyncio.QueueEmpty:
            pass


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
        _MQTT_BROKER,
        _MQTT_PORT,
        _MQTT_CLIENT_ID,
    )

    # Start background task for MQTT message loop
    asyncio.create_task(_mqtt_message_loop())


async def stop_mqtt_client() -> None:
    """Stop the MQTT client daemon."""
    if not _MQTT_ENABLED:
        return
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
            _log.info("MQTT connected to %s:%s", _MQTT_BROKER, _MQTT_PORT)
            client.subscribe(server_sub_filter)
        else:
            _log.warning("MQTT connect failed: rc=%s", reason_code)

    def on_message(client, userdata, msg):
        try:
            payload = _json.loads(msg.payload.decode("utf-8", errors="replace"))
            message_queue.put_nowait((msg.topic, "uplink", payload))
        except Exception:
            _log.debug("MQTT message parse failed topic=%s", msg.topic, exc_info=True)

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        _log.info("MQTT disconnected: rc=%s", reason_code)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.on_connect = on_connect
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
        _MQTT_CLIENT_ID,
        LWT_OFFLINE,
        device_status_topic(_MQTT_CLIENT_ID),
    )

    try:
        client.connect(_MQTT_BROKER, _MQTT_PORT, keepalive=60)
        client.loop_start()
    except Exception as exc:
        _log.error("MQTT connect failed: %s", exc)
        return

    try:
        await _run_mqtt_message_pump(client, message_queue, _json, _time_mod)
    finally:
        _shutdown_mqtt_client(client)
