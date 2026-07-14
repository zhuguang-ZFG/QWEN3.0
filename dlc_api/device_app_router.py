"""Mini-program (device app) route aggregation for the slimmed server_dlc entry.

The WeChat mini-program (v3.9.0+) drives its device management, task dispatch,
gallery, and auth flows through the ``/device/v1/app/*`` routes in
``routes/device_app_*.py``. Those routers used to be registered by the now-deleted
``routes/route_registry.py`` under the old ``server.py`` entry point. After the
slim-down, ``server_dlc.py`` is the sole production entry, so this module
re-attaches the still-active mini-program routers to it.

Only top-level routers are listed here. Sub-routers that are ``include_router``-ed
by their parent are intentionally omitted to avoid double registration:
  - ``device_app_auth_email`` ← included by ``device_app_auth``
  - ``device_app_usage`` ← included by ``device_app_stats``
  - ``device_app_sharing`` ← included by ``device_app_api``
"""

from __future__ import annotations

from fastapi import FastAPI

from routes import (
    device_app_activity,
    device_app_api,
    device_app_assets,
    device_app_auth,
    device_app_chat,
    device_app_gallery,
    device_app_images,
    device_app_members,
    device_app_misc,
    device_app_notifications,
    device_app_provision,
    device_app_stats,
    device_app_status_ws,
    device_app_task_extras,
    device_app_task_templates,
    device_app_tasks,
    device_app_voice,
    device_app_voice_ws,
)

# Top-level mini-program routers, in registration order.
_DEVICE_APP_ROUTERS = (
    device_app_api.router,
    device_app_tasks.router,
    device_app_task_templates.router,
    device_app_task_extras.router,
    device_app_assets.router,
    device_app_members.router,
    device_app_chat.router,
    device_app_auth.router,
    device_app_voice.router,
    device_app_voice_ws.router,
    device_app_notifications.router,
    device_app_provision.router,
    device_app_stats.router,
    device_app_images.router,
    device_app_misc.router,
    device_app_activity.router,
    device_app_status_ws.router,
    device_app_gallery.router,
)


def register_device_app_routes(app: FastAPI) -> None:
    """Attach all active mini-program routers to *app*."""
    for router in _DEVICE_APP_ROUTERS:
        app.include_router(router)
