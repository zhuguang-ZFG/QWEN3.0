#!/usr/bin/env python3
"""Request body examples and dispatch table for the public OpenAPI builder."""

from __future__ import annotations

from typing import Any, Callable

from .shared import uuid


def _req_chat_completions() -> Any:
    return {
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "Hello!"}],
        "temperature": 0.7,
        "stream": False,
    }


def _req_images_generations() -> Any:
    return {
        "model": "dall-e-3",
        "prompt": "A serene mountain lake at sunrise",
        "n": 1,
        "size": "1024x1024",
    }


def _req_auth_login() -> Any:
    # 微信小程序一键登录（jscode2session 换取的 code）
    return {"code": "wx-jscode2session-code"}


def _req_auth_account_delete() -> Any:
    return {"password": "your-password"}


def _req_auth_change_password() -> Any:
    return {"old_password": "old", "new_password": "new"}


def _req_device_bind() -> Any:
    return {"device_id": uuid("dev"), "bind_code": "123456"}


def _req_device_register() -> Any:
    return {"model": "LiMa-Draw-V1", "sn": "SN123456"}


def _req_device_manual_add() -> Any:
    return {"device_id": uuid("dev"), "name": "Living Room"}


def _req_device_discover() -> Any:
    return {"timeout": 10}


def _req_device_pair() -> Any:
    return {"device_id": uuid("dev")}


def _req_device_pair_confirm() -> Any:
    return {"pairing_token": uuid("pair"), "code": "123456"}


def _req_device_provision() -> Any:
    return {"device_id": uuid("dev")}


def _req_device_provision_confirm() -> Any:
    return {"provision_token": uuid("prv"), "code": "123456"}


def _req_device_put() -> Any:
    return {"name": "Living Room", "settings": {}}


def _req_device_unbind() -> Any:
    return {}


def _req_device_supplies_put() -> Any:
    return {"ink": 100, "paper": 100}


def _req_chat_sessions_create() -> Any:
    return {"title": "New chat"}


def _req_device_batch_tasks() -> Any:
    return {"tasks": [{"type": "draw", "prompt": "a cat"}]}


def _req_device_tasks() -> Any:
    return {"type": "draw", "prompt": "a cat"}


def _req_device_batch_draw() -> Any:
    return {"device_ids": [uuid("dev")], "prompt": "a cat"}


def _req_device_voice_tasks_pending() -> Any:
    return {"task_ids": [uuid("tsk")]}


def _req_assets_create() -> Any:
    return {"title": "Cat line art", "prompt": "A cute cat", "category": "animal"}


def _req_asset_render() -> Any:
    return {"device_id": uuid("dev")}


def _req_voiceprints_enroll() -> Any:
    return {"device_id": uuid("dev"), "audio_url": "https://example/voice.wav"}


def _req_voiceprint_put() -> Any:
    return {"name": "Owner"}


def _req_members_create() -> Any:
    return {"phone": "+86-13800000000", "role": "member"}


def _req_transfer_accept() -> Any:
    return {"accept": True}


def _req_transfer_cancel() -> Any:
    return {}


def _req_device_transfer() -> Any:
    return {"to_user_phone": "+86-13900000000"}


def _req_device_share_create() -> Any:
    return {"role": "viewer"}


def _req_device_share_revoke() -> Any:
    return {}


def _req_share_accept() -> Any:
    return {}


def _req_notifications_subscribe() -> Any:
    return {"type": "push", "token": "device-push-token"}


def _req_task_preview() -> Any:
    return {"prompt": "a cat"}


def _req_task_templates_create() -> Any:
    return {"name": "Morning sketch", "prompt": "a sunny morning"}


def _req_task_template_execute() -> Any:
    return {"device_id": uuid("dev")}


def _req_task_save_as_template() -> Any:
    return {"name": "Saved template"}


def _req_task_approve() -> Any:
    return {}


def _req_task_reject() -> Any:
    return {"reason": "inappropriate"}


def _generic_request(path: str, method: str) -> Any:
    return {}


_REQUEST_BY_PATH_METHOD: dict[tuple[str, str], Callable[[], Any]] = {
    ("/device/v1/app/devices/{device_id}", "put"): _req_device_put,
    ("/device/v1/app/devices/{device_id}/supplies", "put"): _req_device_supplies_put,
    ("/device/v1/app/devices/{device_id}/chat-sessions", "post"): _req_chat_sessions_create,
    ("/device/v1/app/assets", "post"): _req_assets_create,
    ("/device/v1/app/tasks/templates", "post"): _req_task_templates_create,
    ("/device/v1/app/voiceprints/{voiceprint_id}", "put"): _req_voiceprint_put,
}

_REQUEST_BY_PATH: dict[str, Callable[[], Any]] = {
    "/v1/chat/completions": _req_chat_completions,
    "/v1/images/generations": _req_images_generations,
    "/device/v1/app/auth/login": _req_auth_login,
    "/device/v1/app/auth/account/delete": _req_auth_account_delete,
    "/device/v1/app/auth/change-password": _req_auth_change_password,
    "/device/v1/app/devices/bind": _req_device_bind,
    "/device/v1/app/devices/register": _req_device_register,
    "/device/v1/app/devices/manual-add": _req_device_manual_add,
    "/device/v1/app/devices/discover": _req_device_discover,
    "/device/v1/app/devices/pair": _req_device_pair,
    "/device/v1/app/devices/pair/confirm": _req_device_pair_confirm,
    "/device/v1/app/devices/provision": _req_device_provision,
    "/device/v1/app/devices/provision/confirm": _req_device_provision_confirm,
    "/device/v1/app/devices/{device_id}/unbind": _req_device_unbind,
    "/device/v1/app/devices/{device_id}/batch-tasks": _req_device_batch_tasks,
    "/device/v1/app/devices/{device_id}/tasks": _req_device_tasks,
    "/device/v1/app/devices/batch-draw": _req_device_batch_draw,
    "/device/v1/app/devices/{device_id}/voice-tasks/pending": _req_device_voice_tasks_pending,
    "/device/v1/app/assets/{asset_id}/render": _req_asset_render,
    "/device/v1/app/voiceprints/enroll": _req_voiceprints_enroll,
    "/device/v1/app/members": _req_members_create,
    "/device/v1/app/transfers/{transfer_id}/accept": _req_transfer_accept,
    "/device/v1/app/transfers/{transfer_id}/cancel": _req_transfer_cancel,
    "/device/v1/app/devices/{device_id}/transfer": _req_device_transfer,
    "/device/v1/app/devices/{device_id}/share": _req_device_share_create,
    "/device/v1/app/devices/{device_id}/share/revoke": _req_device_share_revoke,
    "/device/v1/app/shares/{share_token}/accept": _req_share_accept,
    "/device/v1/app/notifications/subscribe": _req_notifications_subscribe,
    "/device/v1/app/tasks/preview": _req_task_preview,
    "/device/v1/app/tasks/templates/{template_id}/execute": _req_task_template_execute,
    "/device/v1/app/tasks/{task_id}/save-as-template": _req_task_save_as_template,
    "/device/v1/app/tasks/{task_id}/approve": _req_task_approve,
    "/device/v1/app/tasks/{task_id}/reject": _req_task_reject,
}


def request_example(path: str, method: str) -> Any | None:
    """Generate a plausible request body example, or None for body-less methods."""
    method = method.lower()
    if method not in {"post", "put", "patch"}:
        return None
    key = (path, method)
    if key in _REQUEST_BY_PATH_METHOD:
        return _REQUEST_BY_PATH_METHOD[key]()
    if path in _REQUEST_BY_PATH:
        return _REQUEST_BY_PATH[path]()
    return _generic_request(path, method)
