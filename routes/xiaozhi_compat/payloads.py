"""Row → API payload mappers for XiaoZhi v1 compat."""

from __future__ import annotations

from typing import Any

import sqlite3

from .http_helpers import loads_json


def device_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "deviceId": row["id"],
        "deviceSn": row["device_sn"],
        "model": row["model"],
        "firmwareVer": row["firmware_ver"],
        "hardwareVer": row["hardware_ver"],
        "status": row["status"],
        "lastHeartbeat": row["last_heartbeat"],
        "mqttTopic": row["mqtt_topic"],
        "metadata": row["metadata"],
    }


def task_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "taskId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "capability": row["intent"],
        "params": loads_json(row["params"]),
        "source": row["source"],
        "status": row["status"],
        "progress": row["progress"],
        "errorMsg": row["error_msg"],
        "memberId": row["member_id"],
        "createdAt": row["created_at"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
    }


def member_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "memberId": row["id"],
        "id": row["id"],
        "accountId": row["account_id"],
        "deviceId": row["device_id"],
        "name": row["name"],
        "role": row["role"],
        "avatarUrl": row["avatar_url"],
        "voiceprintId": row["voiceprint_id"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def voiceprint_payload(row: sqlite3.Row, member_name: str = "") -> dict[str, Any]:
    return {
        "voiceprintId": row["id"],
        "id": row["id"],
        "memberId": row["member_id"],
        "memberName": member_name,
        "deviceId": row["device_id"],
        "sampleCount": row["sample_count"],
        "confidence": row["confidence"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def transfer_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "transferId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "fromAccountId": row["from_account_id"],
        "toAccountId": row["to_account_id"],
        "status": row["status"],
        "reason": row["reason"],
        "expiresAt": row["expires_at"],
        "acceptedAt": row["accepted_at"],
        "cancelledAt": row["cancelled_at"],
        "createdAt": row["created_at"],
    }


def supply_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "supplyId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "supplyType": row["supply_type"],
        "level": row["level"],
        "status": row["status"],
        "lastReplaced": row["last_replaced"],
        "nextReplacement": row["next_replacement"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def self_check_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "deviceId": row["device_id"],
        "checkType": row["check_type"],
        "result": row["result"],
        "details": row["details"],
        "durationMs": row["duration_ms"],
        "triggeredBy": row["triggered_by"],
        "createdAt": row["created_at"],
    }
