"""MQTT topic contract for LiMa Device Gateway.

Defines the standard MQTT topic structure for device communication.
Compatible with Mosquitto, EMQX, and other MQTT 3.1.1/5.0 brokers.

Topic hierarchy:
  lima/{device_id}/uplink      — device → server (JSON frames)
  lima/{device_id}/downlink    — server → device (JSON frames)
  lima/{device_id}/status      — LWT (Last Will Testament)
  lima/broadcast                — server → all devices

Message format: same JSON frames as WebSocket protocol (lima-device-v1).
"""

from __future__ import annotations

# Topic prefixes
TOPIC_PREFIX = "lima"
UPLINK_TOPIC = "lima/{device_id}/uplink"
DOWNLINK_TOPIC = "lima/{device_id}/downlink"
STATUS_TOPIC = "lima/{device_id}/status"
BROADCAST_TOPIC = "lima/broadcast"

# QoS levels
UPLINK_QOS = 1  # at-least-once for device telemetry
DOWNLINK_QOS = 1  # at-least-once for commands
STATUS_QOS = 0  # best-effort for LWT

# LWT (Last Will Testament) payload
LWT_ONLINE = '{"status":"online"}'
LWT_OFFLINE = '{"status":"offline"}'

# Topic filter for server subscription (all device uplinks)
SERVER_SUB_FILTER = "lima/+/uplink"


def device_uplink_topic(device_id: str) -> str:
    """Topic a device publishes telemetry/events to."""
    return UPLINK_TOPIC.format(device_id=device_id)


def device_downlink_topic(device_id: str) -> str:
    """Topic the server publishes commands to."""
    return DOWNLINK_TOPIC.format(device_id=device_id)


def device_status_topic(device_id: str) -> str:
    """Topic for LWT / device presence."""
    return STATUS_TOPIC.format(device_id=device_id)
