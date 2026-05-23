import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

import server
from routes.images import ImageRequest
from access_guard import require_private_api_key


def _route_for(path: str, method: str) -> APIRoute:
    for route in server.app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


def test_image_generation_requires_private_api_key_dependency():
    route = _route_for("/v1/images/generations", "POST")

    dependency_calls = [dep.call for dep in route.dependant.dependencies]

    assert require_private_api_key in dependency_calls


def test_image_request_rejects_oversized_dimensions():
    with pytest.raises(ValidationError):
        ImageRequest(prompt="red circle", size="4096x4096")
