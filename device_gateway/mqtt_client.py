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
    """Main MQTT message processing loop using paho-mqtt.

    Requires: pip install paho-mqtt
    The MQTT client runs paho's network loop in a background thread
    and bridges incoming messages to asyncio via queues.
    """
    try:
        import paho.mqtt.client as mqtt
        import json as _json
        import time as _time_mod
    except ImportError:
        _log.info("paho-mqtt not installed; MQTT transport remains in stub mode")
        _log.info("Install: pip install paho-mqtt")
        while True:
            await asyncio.sleep(3600)
        return  # unreachable

    from device_gateway.mqtt_topics import (
        LWT_OFFLINE, LWT_ONLINE, SERVER_SUB_FILTER,
        device_downlink_topic, device_status_topic, device_uplink_topic,
    )

    # Bridging: paho (sync) → asyncio
    message_queue: asyncio.Queue[tuple[str, str, dict]] = asyncio.Queue()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            _log.info("MQTT connected to %s:%s", _MQTT_BROKER, _MQTT_PORT)
            client.subscribe(SERVER_SUB_FILTER)
            _log.info("MQTT subscribed: %s", SERVER_SUB_FILTER)
        else:
            _log.warning("MQTT connect failed: rc=%s", reason_code)

    def on_message(client, userdata, msg):
        try:
            topic = msg.topic
            payload = _json.loads(msg.payload.decode("utf-8", errors="replace"))
            message_queue.put_nowait((topic, "uplink", payload))
        except Exception:
            _log.debug("MQTT message parse failed topic=%s", msg.topic, exc_info=True)

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        _log.info("MQTT disconnected: rc=%s", reason_code)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=_MQTT_CLIENT_ID,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # LWT
    client.will_set(
        device_status_topic(_MQTT_CLIENT_ID),
        LWT_OFFLINE, qos=0, retain=True,
    )

    # Connect
    try:
        client.connect(_MQTT_BROKER, _MQTT_PORT, keepalive=60)
        client.loop_start()
        _log.info("MQTT loop started: broker=%s:%s id=%s", _MQTT_BROKER, _MQTT_PORT, _MQTT_CLIENT_ID)
    except Exception as exc:
        _log.warning("MQTT connect failed: %s (broker running?)", exc)
        client.loop_start()
        _log.info("MQTT will retry connection automatically")

    # Main loop: process incoming messages + drain downlink queues
    try:
        while True:
            try:
                topic, direction, payload = await asyncio.wait_for(
                    message_queue.get(), timeout=1.0,
                )
                # Parse device_id from topic: lima/{device_id}/uplink
                parts = topic.split("/")
                device_id = parts[1] if len(parts) > 1 else ""
                msg_type = payload.get("type", "")

                if msg_type == "hello" and device_id:
                    register_mqtt_device(device_id)
                    from device_gateway.mqtt_topics import device_downlink_topic
                    ack = {"type": "hello_ack", "protocol": "lima-device-v1",
                           "device_id": device_id, "server_time": int(_time_mod.time())}
                    client.publish(
                        device_downlink_topic(device_id),
                        _json.dumps(ack), qos=1,
                    )

                if msg_type == "heartbeat" and device_id:
                    ack = {"type": "heartbeat_ack", "device_id": device_id,
                           "server_time": int(_time_mod.time())}
                    client.publish(
                        device_downlink_topic(device_id),
                        _json.dumps(ack), qos=0,
                    )

                if msg_type == "motion_event" and device_id:
                    # Forward to the WebSocket handler for ledger/card/ack
                    try:
                        from routes.device_gateway_ws_handlers import handle_motion_event
                        await handle_motion_event(device_id, payload, None)
                    except Exception:
                        _log.debug("motion event forward failed", exc_info=True)

            except asyncio.TimeoutError:
                pass

            # Drain downlink queues
            for did, queue in list(_mqtt_devices.items()):
                try:
                    while True:
                        msg = queue.get_nowait()
                        client.publish(
                            device_downlink_topic(did),
                            _json.dumps(msg), qos=1,
                        )
                except asyncio.QueueEmpty:
                    pass

    finally:
        client.loop_stop()
        client.disconnect()
        _log.info("MQTT transport stopped")
