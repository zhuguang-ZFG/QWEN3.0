from fastapi.routing import APIRoute, APIWebSocketRoute

import server


def test_server_registers_device_gateway_routes():
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}
    ws_paths = {route.path for route in server.app.routes if isinstance(route, APIWebSocketRoute)}

    assert "/device/v1/health" in http_paths
    assert "/device/v1/events" in http_paths
    assert "/device/v1/tasks" in http_paths
    assert "/device/v1/ws" in ws_paths


def test_server_registers_device_gateway_query_routes_after_extraction():
    """Lock the R-batch extraction: the three GET query endpoints live in
    ``routes.device_gateway_query_routes`` (independent router sharing the
    ``/device/v1`` prefix) and must still be registered on ``server.app``.
    Guards against accidental route-loss during the split.
    """
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}

    # Task status + task list + drawing history — all moved to query_routes.
    assert "/device/v1/tasks/{task_id}" in http_paths
    assert "/device/v1/devices/{device_id}/history" in http_paths

    # The query_routes module owns its own APIRouter instance.
    from routes import device_gateway_query_routes

    assert device_gateway_query_routes.router.prefix == "/device/v1"
    query_paths = {r.path for r in device_gateway_query_routes.router.routes if isinstance(r, APIRoute)}
    # APIRoute.path includes the router prefix, so paths are fully qualified.
    assert "/device/v1/tasks/{task_id}" in query_paths
    assert "/device/v1/tasks" in query_paths
    assert "/device/v1/devices/{device_id}/history" in query_paths


def test_server_registers_device_gateway_events_routes_after_extraction():
    """Lock the S-batch extraction: POST /events lives in
    ``routes.device_gateway_events_routes`` (independent router sharing the
    ``/device/v1`` prefix) and must still be registered on ``server.app``.
    Guards against accidental route-loss during the split.
    """
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}

    assert "/device/v1/events" in http_paths

    from routes import device_gateway_events_routes

    assert device_gateway_events_routes.router.prefix == "/device/v1"
    event_paths = {r.path for r in device_gateway_events_routes.router.routes if isinstance(r, APIRoute)}
    assert "/device/v1/events" in event_paths
