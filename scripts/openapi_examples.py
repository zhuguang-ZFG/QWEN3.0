#!/usr/bin/env python3
"""Request/response example helpers for the public OpenAPI builder.

Each helper returns a plausible JSON example for a public endpoint.
"""

from __future__ import annotations

from typing import Any, Callable


__all__ = [
    "parameter_with_example",
    "request_example",
    "response_example",
    "synthetic_query_param",
    "uuid",
]


def uuid(prefix: str) -> str:
    return f"{prefix}-00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Response examples
# ---------------------------------------------------------------------------

def _resp_chat_completions() -> Any:
    return {
        "id": "chatcmpl-example",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello! How can I help you?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


def _resp_images_generations() -> Any:
    return {
        "created": 1700000000,
        "data": [
            {
                "url": "https://example.cdn/images/generated_001.png",
                "revised_prompt": "A serene mountain lake at sunrise",
            }
        ],
    }


def _resp_auth_login() -> Any:
    return {"access_token": uuid("tok"), "token_type": "bearer", "expires_in": 3600}


def _resp_auth_me() -> Any:
    return {"id": uuid("usr"), "phone": "+86-13800000000", "nickname": "User"}


def _resp_auth_register() -> Any:
    return {"id": uuid("usr"), "message": "registered"}


def _resp_auth_sms_verification() -> Any:
    return {"success": True, "message": "code sent"}


def _resp_auth_account_delete() -> Any:
    return {"success": True}


def _resp_auth_captcha() -> Any:
    return {"captcha_id": uuid("cap"), "image_url": "https://example/captcha.png"}


def _resp_auth_change_password() -> Any:
    return {"success": True}


def _resp_devices_list() -> Any:
    return {
        "items": [
            {"id": uuid("dev"), "name": "Living Room", "model": "LiMa-Draw-V1", "online": True}
        ],
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


def _resp_chat_sessions_list() -> Any:
    return {"sessions": [{"id": uuid("sess"), "title": "New chat"}]}


def _resp_chat_sessions_create() -> Any:
    return {"id": uuid("sess"), "title": "New chat"}


def _resp_chat_session_messages() -> Any:
    return {"messages": [{"role": "user", "content": "Hi"}]}


def _resp_chat_session_delete() -> Any:
    return {"deleted": True}


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


def _resp_assets_list() -> Any:
    return {"assets": [{"id": uuid("ast"), "title": "Cat line art"}]}


def _resp_assets_create() -> Any:
    return {"id": uuid("ast"), "title": "Cat line art"}


def _resp_asset_get() -> Any:
    return {"id": uuid("ast"), "title": "Cat line art", "prompt": "A cute cat"}


def _resp_asset_render() -> Any:
    return {"render_id": uuid("rnd"), "status": "queued"}


def _resp_voiceprints_enroll() -> Any:
    return {"voiceprint_id": uuid("vpr"), "status": "enrolling"}


def _resp_voiceprint_get() -> Any:
    return {"id": uuid("vpr"), "name": "Owner"}


def _resp_voiceprint_put() -> Any:
    return {"id": uuid("vpr"), "updated": True}


def _resp_voiceprint_delete() -> Any:
    return {"deleted": True}


def _resp_members_create() -> Any:
    return {"member_id": uuid("mbr"), "role": "member"}


def _resp_transfers_pending() -> Any:
    return {"transfers": [{"id": uuid("trf"), "device_name": "Bedroom"}]}


def _resp_transfer_accept() -> Any:
    return {"transfer_id": uuid("trf"), "status": "accepted"}


def _resp_transfer_cancel() -> Any:
    return {"transfer_id": uuid("trf"), "status": "cancelled"}


def _resp_device_transfer() -> Any:
    return {"transfer_id": uuid("trf"), "expires_in": 86400}


def _resp_device_shares() -> Any:
    return {"shares": [{"token": uuid("shr"), "role": "viewer"}]}


def _resp_device_share_create() -> Any:
    return {"share_token": uuid("shr"), "status": "active"}


def _resp_device_share_revoke() -> Any:
    return {"revoked": True}


def _resp_share_accept() -> Any:
    return {"share_token": uuid("shr"), "status": "accepted"}


def _resp_notifications_subscribe() -> Any:
    return {"subscription_id": uuid("sub"), "status": "active"}


def _resp_notifications_subscriptions() -> Any:
    return {"subscriptions": [{"id": uuid("sub"), "type": "push"}]}


def _resp_notifications_subscription_delete() -> Any:
    return {"deleted": True}


def _resp_stats_overview() -> Any:
    return {"total_devices": 1, "total_tasks": 42}


def _resp_tasks_list() -> Any:
    return {"tasks": [{"id": uuid("tsk"), "status": "pending"}]}


def _resp_task_get() -> Any:
    return {"id": uuid("tsk"), "status": "done", "result_url": "https://example/result.png"}


def _resp_task_preview() -> Any:
    return {"preview_url": "https://example/preview.png"}


def _resp_task_templates_list() -> Any:
    return {"templates": [{"id": uuid("tpl"), "name": "Morning sketch"}]}


def _resp_task_templates_create() -> Any:
    return {"id": uuid("tpl"), "name": "Morning sketch"}


def _resp_task_template_execute() -> Any:
    return {"task_id": uuid("tsk"), "status": "queued"}


def _resp_task_save_as_template() -> Any:
    return {"template_id": uuid("tpl"), "saved": True}


def _resp_task_approve() -> Any:
    return {"task_id": uuid("tsk"), "status": "approved"}


def _resp_task_reject() -> Any:
    return {"task_id": uuid("tsk"), "status": "rejected"}


def _resp_task_timeline() -> Any:
    return {"events": [{"time": "2024-01-01T00:00:00Z", "status": "created"}]}


def _generic_response(path: str, method: str) -> Any:
    return {"success": True}


_RESPONSE_BY_PATH_METHOD: dict[tuple[str, str], Callable[[], Any]] = {
    ("/device/v1/app/devices", "get"): _resp_devices_list,
    ("/device/v1/app/devices/{device_id}", "get"): _resp_device_get,
    ("/device/v1/app/devices/{device_id}", "put"): _resp_device_put,
    ("/device/v1/app/devices/{device_id}/supplies", "get"): _resp_device_supplies_get,
    ("/device/v1/app/devices/{device_id}/supplies", "put"): _resp_device_supplies_put,
    ("/device/v1/app/devices/{device_id}/chat-sessions", "get"): _resp_chat_sessions_list,
    ("/device/v1/app/devices/{device_id}/chat-sessions", "post"): _resp_chat_sessions_create,
    ("/device/v1/app/assets", "get"): _resp_assets_list,
    ("/device/v1/app/assets", "post"): _resp_assets_create,
    ("/device/v1/app/voiceprints/{voiceprint_id}", "put"): _resp_voiceprint_put,
    ("/device/v1/app/voiceprints/{voiceprint_id}", "delete"): _resp_voiceprint_delete,
    ("/device/v1/app/tasks", "get"): _resp_tasks_list,
    ("/device/v1/app/tasks/{task_id}", "get"): _resp_task_get,
    ("/device/v1/app/tasks/templates", "get"): _resp_task_templates_list,
    ("/device/v1/app/tasks/templates", "post"): _resp_task_templates_create,
    ("/device/v1/app/notifications/subscriptions", "get"): _resp_notifications_subscriptions,
    ("/device/v1/app/notifications/subscriptions/{sub_id}", "delete"): _resp_notifications_subscription_delete,
    ("/device/v1/app/devices/{device_id}/voiceprints", "get"): _resp_device_voiceprints,
}

_RESPONSE_BY_PATH: dict[str, Callable[[], Any]] = {
    "/v1/chat/completions": _resp_chat_completions,
    "/v1/images/generations": _resp_images_generations,
    "/device/v1/app/auth/login": _resp_auth_login,
    "/device/v1/app/auth/me": _resp_auth_me,
    "/device/v1/app/auth/register": _resp_auth_register,
    "/device/v1/app/auth/sms-verification": _resp_auth_sms_verification,
    "/device/v1/app/auth/account/delete": _resp_auth_account_delete,
    "/device/v1/app/auth/captcha": _resp_auth_captcha,
    "/device/v1/app/auth/change-password": _resp_auth_change_password,
    "/device/v1/app/devices/bind": _resp_device_bind,
    "/device/v1/app/devices/register": _resp_device_register,
    "/device/v1/app/devices/manual-add": _resp_device_manual_add,
    "/device/v1/app/devices/discover": _resp_device_discover,
    "/device/v1/app/devices/pair": _resp_device_pair,
    "/device/v1/app/devices/pair/confirm": _resp_device_pair_confirm,
    "/device/v1/app/devices/provision": _resp_device_provision,
    "/device/v1/app/devices/provision/confirm": _resp_device_provision_confirm,
    "/device/v1/app/devices/{device_id}/unbind": _resp_device_unbind,
    "/device/v1/app/devices/{device_id}/status": _resp_device_status,
    "/device/v1/app/devices/{device_id}/stats": _resp_device_stats,
    "/device/v1/app/devices/{device_id}/activity": _resp_device_activity,
    "/device/v1/app/devices/{device_id}/self-checks": _resp_device_self_checks,
    "/device/v1/app/devices/{device_id}/members": _resp_device_members,
    "/device/v1/app/devices/{device_id}/chat-sessions/{session_id}/messages": _resp_chat_session_messages,
    "/device/v1/app/chat-sessions/{session_id}": _resp_chat_session_delete,
    "/device/v1/app/devices/{device_id}/chat-history": _resp_device_chat_history,
    "/device/v1/app/devices/{device_id}/audio/{audio_id}": _resp_device_audio,
    "/device/v1/app/devices/batch-draw": _resp_device_batch_draw,
    "/device/v1/app/devices/{device_id}/batch-tasks": _resp_device_batch_tasks,
    "/device/v1/app/devices/{device_id}/tasks": _resp_device_tasks,
    "/device/v1/app/devices/{device_id}/voice-tasks/pending": _resp_device_voice_tasks_pending,
    "/device/v1/app/assets/{asset_id}": _resp_asset_get,
    "/device/v1/app/assets/{asset_id}/render": _resp_asset_render,
    "/device/v1/app/voiceprints/enroll": _resp_voiceprints_enroll,
    "/device/v1/app/voiceprints/{voiceprint_id}": _resp_voiceprint_get,
    "/device/v1/app/members": _resp_members_create,
    "/device/v1/app/transfers/pending": _resp_transfers_pending,
    "/device/v1/app/transfers/{transfer_id}/accept": _resp_transfer_accept,
    "/device/v1/app/transfers/{transfer_id}/cancel": _resp_transfer_cancel,
    "/device/v1/app/devices/{device_id}/transfer": _resp_device_transfer,
    "/device/v1/app/devices/{device_id}/shares": _resp_device_shares,
    "/device/v1/app/devices/{device_id}/share": _resp_device_share_create,
    "/device/v1/app/devices/{device_id}/share/revoke": _resp_device_share_revoke,
    "/device/v1/app/shares/{share_token}/accept": _resp_share_accept,
    "/device/v1/app/notifications/subscribe": _resp_notifications_subscribe,
    "/device/v1/app/stats/overview": _resp_stats_overview,
    "/device/v1/app/tasks/preview": _resp_task_preview,
    "/device/v1/app/tasks/templates/{template_id}/execute": _resp_task_template_execute,
    "/device/v1/app/tasks/{task_id}/save-as-template": _resp_task_save_as_template,
    "/device/v1/app/tasks/{task_id}/approve": _resp_task_approve,
    "/device/v1/app/tasks/{task_id}/reject": _resp_task_reject,
    "/device/v1/app/tasks/{task_id}/timeline": _resp_task_timeline,
}


def response_example(path: str, method: str) -> Any:
    """Generate a plausible JSON response example for an endpoint."""
    method = method.lower()
    key = (path, method)
    if key in _RESPONSE_BY_PATH_METHOD:
        return _RESPONSE_BY_PATH_METHOD[key]()
    if path in _RESPONSE_BY_PATH:
        return _RESPONSE_BY_PATH[path]()
    return _generic_response(path, method)


# ---------------------------------------------------------------------------
# Request examples
# ---------------------------------------------------------------------------

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
    return {
        "phone": "+86-13800000000",
        "password": "your-password",
        "captcha_id": uuid("cap"),
        "captcha_code": "1234",
    }


def _req_auth_register() -> Any:
    return {"phone": "+86-13800000000", "password": "your-password", "sms_code": "123456"}


def _req_auth_sms_verification() -> Any:
    return {"phone": "+86-13800000000", "purpose": "register"}


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
    "/device/v1/app/auth/register": _req_auth_register,
    "/device/v1/app/auth/sms-verification": _req_auth_sms_verification,
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


# ---------------------------------------------------------------------------
# Parameter examples
# ---------------------------------------------------------------------------

def synthetic_query_param(path: str) -> dict[str, Any]:
    """Create a plausible optional query parameter when an endpoint has none."""
    if "/auth/captcha" in path:
        return {
            "name": "width",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "default": 120, "title": "Width"},
        }
    return {
        "name": "locale",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "zh-CN", "title": "Locale"},
    }


def parameter_with_example(param: dict[str, Any]) -> dict[str, Any]:
    """Attach a sensible example to a parameter for request examples."""
    param = dict(param)
    name = param.get("name", "")
    schema = param.get("schema", {})
    typ = schema.get("type") if isinstance(schema, dict) else None

    if name == "authorization":
        example = "Bearer lima_api_token"
    elif name == "device_id":
        example = uuid("dev")
    elif name == "asset_id":
        example = uuid("ast")
    elif name == "session_id":
        example = uuid("sess")
    elif name == "task_id":
        example = uuid("tsk")
    elif name == "template_id":
        example = uuid("tpl")
    elif name == "voiceprint_id":
        example = uuid("vpr")
    elif name == "sub_id":
        example = uuid("sub")
    elif name == "transfer_id":
        example = uuid("trf")
    elif name == "share_token":
        example = uuid("shr")
    elif name == "audio_id":
        example = uuid("aud")
    elif typ == "integer":
        example = schema.get("default", 1)
    elif typ == "boolean":
        example = True
    else:
        example = schema.get("default") if schema.get("default") not in (None, "") else f"example_{name}"

    param["example"] = example
    return param
