"""Tests for routes/handwriting.py."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.autohanding import constants
from integrations.autohanding.client import AutohandingClientError, AutohandingRateLimitError
from routes import handwriting as hw


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(hw.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


@pytest.fixture(autouse=True)
def _patch_auth(account):
    with patch.object(hw, "authorize", return_value=account):
        yield


def _svg_result():
    return {
        "status": "success",
        "svg_path": "M 0 0 L 10 10",
        "width": 100,
        "height": 200,
    }


def _patch_autohanding_and_converter(svg_result=None, side_effect=None):
    stack = ExitStack()
    stack.enter_context(
        patch.object(
            hw.autohanding_client,
            "convert_text",
            AsyncMock(return_value=b"png-bytes", side_effect=side_effect),
        )
    )
    if svg_result is not None:
        converter = MagicMock()
        converter.convert_bytes_to_svg = AsyncMock(return_value=svg_result)
        stack.enter_context(patch.object(hw, "SVGConverter", return_value=converter))
    return stack


def test_handwriting_success(client, auth_header):
    with _patch_autohanding_and_converter(svg_result=_svg_result()):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello"},
            headers=auth_header,
        )

    assert response.status_code == 200
    data = response.json()["data"][0]
    assert data["svg_path"] == "M 0 0 L 10 10"
    assert data["backend"] == "autohanding"


def test_handwriting_disabled(client, auth_header):
    with patch.object(hw, "_ENABLED", False):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello"},
            headers=auth_header,
        )
    assert response.status_code == 503


def test_handwriting_invalid_request(client, auth_header):
    response = client.post(
        "/device/v1/app/handwriting",
        json={},
        headers=auth_header,
    )
    assert response.status_code == 400


def test_handwriting_autohanding_rate_limit(client, auth_header):
    with patch.object(
        hw.autohanding_client,
        "convert_text",
        AsyncMock(side_effect=AutohandingRateLimitError("limit")),
    ):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello"},
            headers=auth_header,
        )

    assert response.status_code == 429


def test_handwriting_vectorization_failure(client, auth_header):
    with _patch_autohanding_and_converter(svg_result={"status": "failed", "error": "no strokes"}):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello"},
            headers=auth_header,
        )

    assert response.status_code == 502


def test_handwriting_task_mode(client, auth_header):
    task_params = {
        "feed": 1000,
        "path": [{"x": 0, "y": 0, "z": 0}],
        "source_capability": "handwriting",
        "text": "hello",
        "preview_svg": "<svg></svg>",
    }
    with patch.object(hw, "build_handwriting_params", AsyncMock(return_value=(task_params, None))) as mock_build:
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello", "mode": "task"},
            headers=auth_header,
        )
        mock_build.assert_awaited_once()

    assert response.status_code == 200
    data = response.json()["data"][0]
    assert data["source_capability"] == "handwriting"


def test_handwriting_task_mode_autohanding_fallback(client, auth_header):
    with patch.object(
        hw.autohanding_client,
        "convert_text",
        AsyncMock(side_effect=AutohandingClientError("boom")),
    ):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello fallback", "mode": "task"},
            headers=auth_header,
        )

    assert response.status_code == 200
    data = response.json()["data"][0]
    assert data["source_capability"] == "handwriting"
    assert data["backend"] == "lima-local"
    assert data["path"]


def test_handwriting_autohanding_error_ascii_fallback(client, auth_header):
    with patch.object(
        hw.autohanding_client,
        "convert_text",
        AsyncMock(side_effect=AutohandingClientError("boom")),
    ):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "hello"},
            headers=auth_header,
        )

    assert response.status_code == 200
    data = response.json()["data"][0]
    assert data["backend"] == "lima-local"
    assert data["svg_path"].startswith("M")


def test_handwriting_autohanding_error_no_fallback_for_chinese(client, auth_header):
    with patch.object(
        hw.autohanding_client,
        "convert_text",
        AsyncMock(side_effect=AutohandingClientError("boom")),
    ):
        response = client.post(
            "/device/v1/app/handwriting",
            json={"text": "你好"},
            headers=auth_header,
        )

    assert response.status_code == 502


def test_handwriting_options(client, auth_header):
    response = client.get("/device/v1/app/handwriting/options", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert constants.DEFAULT_FONT_TYPE in data["fonts"]
    assert constants.DEFAULT_PAPER_BG_TYPE in data["papers"]
    assert data["defaults"]["font_type"] == constants.DEFAULT_FONT_TYPE
