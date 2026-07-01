"""Basic routes/images tests: auth, validation, generation, recorder."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from routes import images as img
from .conftest import auth_header


def test_missing_auth_returns_401(client):
    response = client.post("/v1/images/generations", json={"prompt": "hi"})
    assert response.status_code == 401


def test_invalid_body_returns_400(client):
    response = client.post("/v1/images/generations", headers=auth_header(), json={"prompt": ""})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"prompt": "hi", "size": "abc"},
        {"prompt": "hi", "size": "3000x3000"},
        {"prompt": "hi", "n": 0},
        {"prompt": "hi", "n": 20},
        {"prompt": "hi", "seed": -2},
    ],
)
def test_validation_errors(client, body):
    response = client.post("/v1/images/generations", headers=auth_header(), json=body)
    assert response.status_code == 400


def test_empty_prompt_returns_400(client):
    response = client.post("/v1/images/generations", headers=auth_header(), json={"prompt": "   "})
    assert response.status_code == 400


def test_successful_generation(client):
    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "a cat", "size": "1024x1024", "n": 2},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert "image.pollinations.ai" in data[0]["url"]
    assert "width=1024" in data[0]["url"]


def test_chinese_prompt_gets_prefixed(client):
    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "小猫"},
    )
    assert response.status_code == 200
    url = response.json()["data"][0]["url"]
    assert "high%20quality%2C%20detailed%2C" in url


def test_record_request_callback(client):
    recorder = MagicMock()
    img.inject_record_request(recorder)
    response = client.post(
        "/v1/images/generations",
        headers=auth_header(),
        json={"prompt": "a dog"},
    )
    assert response.status_code == 200
    recorder.assert_called_once()
    assert recorder.call_args.args[0] == "a dog"
    assert recorder.call_args.args[2] == "image_generation"
