"""Tests for the JDCloud proxy worker."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import Request, status
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from deploy.jdcloud.jdcloud_worker import (
    Config,
    ProviderConfig,
    _build_upstream_headers,
    _check_body_size,
    _resolve_provider,
    _validate_auth,
    app,
    load_config,
)

TEST_TOKEN = "test-worker-token"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a valid worker token and a dummy provider for every test."""
    monkeypatch.setenv("JDCLOUD_WORKER_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TESTPROVIDER_URL", "https://example.com/v1/chat/completions")
    monkeypatch.setenv("TESTPROVIDER_KEY", "provider-secret-key")
    monkeypatch.delenv("JDCLOUD_MAX_BODY_BYTES", raising=False)


@pytest.fixture
def client() -> TestClient:
    """Yield a sync TestClient wired to the ASGI app with lifespan enabled."""
    with TestClient(app) as test_client:
        yield test_client


class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestAuth:
    def test_missing_token_returns_401(self, client: TestClient) -> None:
        response = client.post("/proxy/testprovider", content=b"{}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/proxy/testprovider",
            content=b"{}",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_scheme_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/proxy/testprovider",
            content=b"{}",
            headers={"Authorization": f"Basic {TEST_TOKEN}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestProviderResolution:
    def test_unknown_provider_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/proxy/unknown",
            content=b"{}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProxyForwarding:
    def test_valid_token_forwards_request(self, client: TestClient) -> None:
        captured: dict[str, Any] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = await request.aread()
            return httpx.Response(
                status_code=200,
                json={"choices": [{"message": {"content": "hi"}}]},
            )

        app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post(
            "/proxy/testprovider",
            json={"model": "test-model"},
            headers={
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["choices"][0]["message"]["content"] == "hi"
        assert captured["url"] == "https://example.com/v1/chat/completions"
        assert captured["headers"].get("authorization") == "Bearer provider-secret-key"
        assert captured["body"] == b'{"model":"test-model"}'


class TestKeylessProvider:
    def test_keyless_provider_loads_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLLINATIONS_URL", "https://text.pollinations.ai/openai/chat/completions")
        monkeypatch.delenv("POLLINATIONS_KEY", raising=False)
        cfg = Config()
        assert "pollinations" in cfg.providers
        assert cfg.providers["pollinations"].key == ""
        assert cfg.providers["pollinations"].url == "https://text.pollinations.ai/openai/chat/completions"

    def test_keyless_provider_forwards_without_authorization(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLLINATIONS_URL", "https://text.pollinations.ai/openai/chat/completions")
        monkeypatch.delenv("POLLINATIONS_KEY", raising=False)

        captured: dict[str, Any] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            return httpx.Response(status_code=200, json={"choices": [{"message": {"content": "ok"}}]})

        with TestClient(app) as client:
            app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            response = client.post(
                "/proxy/pollinations",
                json={"model": "openai"},
                headers={
                    "Authorization": f"Bearer {TEST_TOKEN}",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert captured["url"] == "https://text.pollinations.ai/openai/chat/completions"
        assert "authorization" not in captured["headers"]

    def test_build_upstream_headers_omits_authorization_when_no_key(self) -> None:
        scope = {"type": "http", "headers": Headers({"host": "test", "x-custom": "ok"}).raw}
        request = Request(scope)
        headers = _build_upstream_headers(request, "")
        assert "Authorization" not in headers
        assert headers["x-custom"] == "ok"


class TestBodySizeLimit:
    def test_oversized_body_returns_413(self, client: TestClient) -> None:
        big_body = b'{"x":"' + b"a" * (11 * 1024 * 1024) + b'"}'
        response = client.post(
            "/proxy/testprovider",
            content=big_body,
            headers={
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Content-Type": "application/json",
                "Content-Length": str(len(big_body)),
            },
        )
        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE

    def test_missing_content_length_returns_413(self) -> None:
        headers = Headers({"content-type": "application/json"})
        request = Request({"type": "http", "headers": headers.raw})
        with pytest.raises(Exception) as exc_info:  # noqa: PT011
            _check_body_size(request, 10 * 1024 * 1024)
        assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE


class TestSseResponse:
    def test_sse_streaming_response(self, client: TestClient) -> None:
        chunks = ['data: {"ok": true}\n\n', "data: [DONE]\n\n"]

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                headers={"content-type": "text/event-stream"},
                content="".join(chunks).encode(),
            )

        app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        response = client.post(
            "/proxy/testprovider",
            json={"stream": True},
            headers={
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        assert response.text == "".join(chunks)


class TestUnitHelpers:
    def test_validate_auth_accepts_valid_token(self) -> None:
        _validate_auth(f"Bearer {TEST_TOKEN}", TEST_TOKEN)

    def test_validate_auth_rejects_wrong_scheme(self) -> None:
        with pytest.raises(Exception) as exc_info:  # noqa: PT011
            _validate_auth(f"Basic {TEST_TOKEN}", TEST_TOKEN)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_resolve_provider_case_insensitive(self) -> None:
        providers = {"openai": ProviderConfig("url", "key")}
        cfg = _resolve_provider("OpenAI", providers)
        assert cfg.url == "url"

    def test_build_upstream_headers_injects_key_and_drops_host_auth_content_length(
        self,
    ) -> None:
        scope = {"type": "http", "headers": Headers({"host": "test", "x-custom": "ok"}).raw}
        request = Request(scope)
        headers = _build_upstream_headers(request, "provider-key")
        assert headers["Authorization"] == "Bearer provider-key"
        assert headers["x-custom"] == "ok"
        assert "host" not in headers
        assert "content-length" not in headers


class TestConfigLoading:
    def test_load_config_raises_runtime_error_when_token_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JDCLOUD_WORKER_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="JDCLOUD_WORKER_TOKEN"):
            load_config()

    def test_config_max_body_bytes_defaults_to_10mb(self) -> None:
        cfg = Config()
        assert cfg.max_body_bytes == 10 * 1024 * 1024

    def test_config_max_body_bytes_is_customizable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JDCLOUD_MAX_BODY_BYTES", "2048")
        cfg = Config()
        assert cfg.max_body_bytes == 2048
