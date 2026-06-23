"""Tests for routes/embeddings.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import embeddings as emb


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("GFW_PROXY", raising=False)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(emb.router)
    return TestClient(app)


def _auth_header():
    return {"Authorization": "Bearer test-key"}


def test_missing_auth_returns_401(client):
    response = client.post("/v1/embeddings", json={"input": "hello"})
    assert response.status_code == 401


def test_invalid_json_returns_400(client):
    response = client.post("/v1/embeddings", headers=_auth_header(), data="not-json")
    assert response.status_code == 400


@pytest.mark.parametrize(
    "body, expected_substring",
    [
        ({"input": []}, "must not be empty"),
        ({"input": ["a"] * (emb.MAX_EMBEDDING_INPUTS + 1)}, "at most"),
        ({"input": 123}, "string or list of strings"),
        ({"input": "hello", "dimensions": "bad"}, "dimensions must be an integer"),
        ({"input": "hello", "dimensions": 0}, "between"),
        ({"input": "hello", "dimensions": 99999}, "between"),
    ],
)
def test_validation_errors(client, body, expected_substring):
    response = client.post("/v1/embeddings", headers=_auth_header(), json=body)
    assert response.status_code == 400
    assert expected_substring in response.text


def test_missing_jina_key_returns_503(client):
    response = client.post("/v1/embeddings", headers=_auth_header(), json={"input": "hello"})
    assert response.status_code == 503
    assert "JINA_API_KEY" in response.json()["error"]


@patch("httpx.AsyncClient")
def test_successful_embedding_proxy(mock_async_client, client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "jina-key")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_async_client.return_value = mock_client

    response = client.post(
        "/v1/embeddings",
        headers=_auth_header(),
        json={"input": "hello", "dimensions": 128},
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["embedding"] == [0.1, 0.2]
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "jina-embeddings-v3"
    assert call_kwargs["json"]["dimensions"] == 128
    assert "Bearer jina-key" in call_kwargs["headers"]["Authorization"]


@patch("httpx.AsyncClient")
def test_proxy_error_returns_502(mock_async_client, client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "jina-key")
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_async_client.return_value = mock_client

    response = client.post("/v1/embeddings", headers=_auth_header(), json={"input": "hello"})
    assert response.status_code == 502
    assert "boom" in response.json()["error"]
