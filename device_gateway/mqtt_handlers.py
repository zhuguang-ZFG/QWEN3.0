"""MQTT uplink/downlink message handlers used by device_gateway.mqtt_client."""

from __future__ import annotations

import asyncio
import logging

_log = logging.getLogger(__name__)


def _send_hello_ack(client, device_id: str, _json, _time_mod) -> None:
    """Register device and send hello acknowledgement."""
    from device_gateway.mqtt_client import register_mqtt_device
    from device_gateway.mqtt_topics import device_downlink_topic

    register_mqtt_device(device_id)
    ack = {
        "type": "hello_ack",
        "protocol": "lima-device-v1",
        "device_id": device_id,
        "server_time": int(_time_mod.time()),
    }
    client.publish(device_downlink_topic(device_id), _json.dumps(ack), qos=1)


def _send_heartbeat_ack(client, device_id: str, _json, _time_mod) -> None:
    """Send heartbeat acknowledgement to a registered device."""
    from device_gateway.mqtt_client import _mqtt_devices

    if device_id not in _mqtt_devices:
        _log.warning("MQTT heartbeat before hello device=%s", device_id)
        return
    from device_gateway.mqtt_topics import device_downlink_topic

    ack = {"type": "heartbeat_ack", "device_id": device_id, "server_time": int(_time_mod.time())}
    client.publish(device_downlink_topic(device_id), _json.dumps(ack), qos=0)


def _forward_motion_event(device_id: str, message: dict) -> None:
    """Forward a motion event to the WebSocket event handler."""
    from device_gateway.mqtt_client import _main_loop, _mqtt_devices

    if device_id not in _mqtt_devices:
        _log.warning("MQTT motion_event before hello device=%s", device_id)
        return
    try:
        from routes.device_gateway_ws_handlers import handle_motion_event

        loop = _main_loop or asyncio.get_running_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(handle_motion_event(device_id, message, None), loop)
        else:
            _log.warning("MQTT event loop not running; dropping motion_event from device=%s", device_id)
    except (RuntimeError, Exception) as exc:
        _log.warning("MQTT motion event forward failed for device=%s: %s", device_id, exc, exc_info=True)


def _handle_mqtt_message(client, topic: str, payload: dict, _json, _time_mod) -> None:
    """Process a single MQTT uplink message (hello / heartbeat / motion_event)."""
    from device_gateway.auth import validate_device_token
    from device_gateway.mqtt_client import _mqtt_devices
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
        _send_hello_ack(client, device_id, _json, _time_mod)
    elif msg_type == "heartbeat" and device_id:
        _send_heartbeat_ack(client, device_id, _json, _time_mod)
    elif msg_type == "motion_event" and device_id:
        _forward_motion_event(device_id, message)


def _extract_mqtt_token(payload: dict) -> str:
    value = str(payload.get("token") or payload.get("authorization") or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _drain_downlink_queues(client, _json) -> None:
    """Drain per-device downlink queues and publish messages."""
    from device_gateway.mqtt_client import _mqtt_devices
    from device_gateway.mqtt_topics import device_downlink_topic

    for did, q in list(_mqtt_devices.items()):
        try:
            while True:
                msg = q.get_nowait()
                client.publish(device_downlink_topic(did), _json.dumps(msg), qos=1)
        except asyncio.QueueEmpty:
            pass
