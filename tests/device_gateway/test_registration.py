from fastapi.routing import APIRoute, APIWebSocketRoute

import server


def test_server_registers_device_gateway_routes():
    http_paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}
    ws_paths = {route.path for route in server.app.routes if isinstance(route, APIWebSocketRoute)}

    assert "/device/v1/health" in http_paths
    assert "/device/v1/events" in http_paths
    assert "/device/v1/tasks" in http_paths
    assert "/device/v1/ws" in ws_paths
