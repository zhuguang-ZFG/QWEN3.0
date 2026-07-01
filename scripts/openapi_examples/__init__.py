#!/usr/bin/env python3
"""Request/response example helpers for the public OpenAPI builder.

The package exposes the same public API as the original ``openapi_examples.py``
module while keeping each submodule under the project size guideline.
"""

from __future__ import annotations

from typing import Any, Callable

from .requests import request_example
from .shared import parameter_with_example, synthetic_query_param, uuid

# Response builders are imported into dispatch tables rather than re-exported.
from .responses_asset import (
    _resp_asset_get,
    _resp_asset_render,
    _resp_assets_create,
    _resp_assets_list,
    _resp_voiceprint_delete,
    _resp_voiceprint_get,
    _resp_voiceprint_put,
    _resp_voiceprints_enroll,
)
from .responses_auth import (
    _resp_auth_account_delete,
    _resp_auth_change_password,
    _resp_auth_login,
    _resp_auth_me,
)
from .responses_chat import _resp_chat_completions, _resp_images_generations
from .responses_device import (
    _resp_device_activity,
    _resp_device_audio,
    _resp_device_batch_draw,
    _resp_device_batch_tasks,
    _resp_device_bind,
    _resp_device_chat_history,
    _resp_device_discover,
    _resp_device_get,
    _resp_device_manual_add,
    _resp_device_members,
    _resp_device_pair,
    _resp_device_pair_confirm,
    _resp_device_provision,
    _resp_device_provision_confirm,
    _resp_device_register,
    _resp_device_self_checks,
    _resp_device_status,
    _resp_device_stats,
    _resp_device_supplies_get,
    _resp_device_supplies_put,
    _resp_device_tasks,
    _resp_device_unbind,
    _resp_device_voice_tasks_pending,
    _resp_device_voiceprints,
    _resp_devices_list,
    _resp_device_put,
)
from .responses_share import (
    _resp_chat_session_delete,
    _resp_chat_session_messages,
    _resp_chat_sessions_create,
    _resp_chat_sessions_list,
    _resp_device_share_create,
    _resp_device_share_revoke,
    _resp_device_shares,
    _resp_device_transfer,
    _resp_members_create,
    _resp_notifications_subscribe,
    _resp_notifications_subscription_delete,
    _resp_notifications_subscriptions,
    _resp_share_accept,
    _resp_stats_overview,
    _resp_transfer_accept,
    _resp_transfer_cancel,
    _resp_transfers_pending,
)
from .responses_task import (
    _resp_task_approve,
    _resp_task_get,
    _resp_task_preview,
    _resp_task_reject,
    _resp_task_save_as_template,
    _resp_task_template_execute,
    _resp_task_templates_create,
    _resp_task_templates_list,
    _resp_task_timeline,
    _resp_tasks_list,
)


__all__ = [
    "parameter_with_example",
    "request_example",
    "response_example",
    "synthetic_query_param",
    "uuid",
]


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
    "/device/v1/app/auth/account/delete": _resp_auth_account_delete,
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
