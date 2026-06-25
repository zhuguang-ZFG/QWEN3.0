#!/usr/bin/env python3
"""Response examples for device management endpoints."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_devices_list() -> Any:
    return {
        "items": [{"id": uuid("dev"), "name": "Living Room", "model": "LiMa-Draw-V1", "online": True}],
        "total": 1,
    }


def _resp_device_get() -> Any:
    return {"id": uuid("dev"), "name": "Living Room", "model": "LiMa-Draw-V1", "online": True}


def _resp_device_put() -> Any:
    return {"id": uuid("dev"), "name": "Living Room", "updated": True}


def _resp_device_bind() -> Any:
    return {"device_id": uuid("dev"), "bound": True}


def _resp_device_register() -> Any:
    return {"device_id": uuid("dev"), "registered": True}


def _resp_device_manual_add() -> Any:
    return {"device_id": uuid("dev"), "added": True}


def _resp_device_discover() -> Any:
    return {"devices": [{"id": uuid("dev"), "name": "LiMa-Draw-V1", "rssi": -45}]}


def _resp_device_pair() -> Any:
    return {"pairing_token": uuid("pair"), "expires_in": 300}


def _resp_device_pair_confirm() -> Any:
    return {"paired": True, "device_id": uuid("dev")}


def _resp_device_provision() -> Any:
    return {"provision_token": uuid("prv"), "expires_in": 300}


def _resp_device_provision_confirm() -> Any:
    return {"provisioned": True, "device_id": uuid("dev")}


def _resp_device_unbind() -> Any:
    return {"unbound": True}


def _resp_device_status() -> Any:
    return {"device_id": uuid("dev"), "status": "online", "battery": 87}


def _resp_device_stats() -> Any:
    return {"device_id": uuid("dev"), "tasks_total": 42, "tasks_today": 3}


def _resp_device_activity() -> Any:
    return {"activities": [{"time": "2024-01-01T00:00:00Z", "event": "draw_done"}]}


def _resp_device_self_checks() -> Any:
    return {"checks": [{"name": "pen", "status": "ok"}]}


def _resp_device_supplies_get() -> Any:
    return {"device_id": uuid("dev"), "ink": 80, "paper": 65}


def _resp_device_supplies_put() -> Any:
    return {"device_id": uuid("dev"), "updated": True}


def _resp_device_members() -> Any:
    return {"members": [{"id": uuid("usr"), "role": "owner"}]}


def _resp_device_chat_history() -> Any:
    return {"messages": [{"role": "user", "content": "Hi"}]}


def _resp_device_audio() -> Any:
    return {"audio_id": uuid("aud"), "url": "https://example/audio.mp3"}


def _resp_device_batch_draw() -> Any:
    return {"task_id": uuid("tsk"), "queued": True}


def _resp_device_batch_tasks() -> Any:
    return {"task_id": uuid("tsk"), "queued": True}


def _resp_device_tasks() -> Any:
    return {"task_id": uuid("tsk"), "queued": True}


def _resp_device_voice_tasks_pending() -> Any:
    return {"tasks": [{"id": uuid("tsk"), "text": "draw a cat"}]}


def _resp_device_voiceprints() -> Any:
    return {"voiceprints": [{"id": uuid("vpr"), "name": "Owner"}]}
