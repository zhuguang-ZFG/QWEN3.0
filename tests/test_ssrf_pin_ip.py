"""Tests for SSRF pin-IP protection in image_url_validation."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from xiaozhi_drawing.image_url_validation import fetch_pinned, validate_and_pin_ip


# --------------------------------------------------------------------------- #
#  validate_and_pin_ip
# --------------------------------------------------------------------------- #


def _fake_getaddrinfo_private(host, port, *a, **kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]


def _fake_getaddrinfo_private_10(host, port, *a, **kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]


def _fake_getaddrinfo_public(host, port, *a, **kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


class TestValidateAndPinIp:
    def test_rejects_metadata_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_private)
        with pytest.raises(ValueError, match="blocked"):
            validate_and_pin_ip("https://api.telegram.org/image.png")

    def test_rejects_rfc1918(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_private_10)
        with pytest.raises(ValueError, match="blocked"):
            validate_and_pin_ip("https://api.telegram.org/image.png")

    def test_accepts_public_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
        url, pinned_ip, host = validate_and_pin_ip("https://api.telegram.org/image.png")
        assert pinned_ip == "93.184.216.34"
        assert host == "api.telegram.org"

    def test_rejects_empty_url(self):
        with pytest.raises(ValueError, match="required"):
            validate_and_pin_ip("")

    def test_rejects_non_http(self):
        with pytest.raises(ValueError, match="http"):
            validate_and_pin_ip("ftp://evil.com/x.png")

    def test_rejects_direct_private_hostname(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_and_pin_ip("http://127.0.0.1/x.png")


# --------------------------------------------------------------------------- #
#  fetch_pinned
# --------------------------------------------------------------------------- #


class TestFetchPinned:
    @pytest.mark.asyncio
    async def test_sends_to_pinned_ip_with_host_header(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "93.184.216.34"
            assert request.headers["host"] == "api.telegram.org"
            return httpx.Response(200, content=b"PNG_DATA")

        with patch("xiaozhi_drawing.image_url_validation.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)

            async def fake_get(url, **kwargs):
                req = httpx.Request("GET", url, headers=kwargs.get("headers"))
                return await AsyncMock(return_value=httpx.Response(200, content=b"PNG_DATA"))()

            # Use MockTransport for clean assertion
            captured_requests = []

            async def capture_get(url, *, headers=None, extensions=None):
                captured_requests.append((url, headers, extensions))
                req = httpx.Request("GET", url)
                resp = httpx.Response(200, content=b"PNG_DATA", request=req)
                return resp

            mock_instance.get = capture_get
            MockClient.return_value = mock_instance

            result = await fetch_pinned("https://api.telegram.org/image.png")
            assert result == b"PNG_DATA"
            assert len(captured_requests) == 1
            req_url, req_headers, req_ext = captured_requests[0]
            assert "93.184.216.34" in req_url
            assert req_headers["Host"] == "api.telegram.org"

    @pytest.mark.asyncio
    async def test_rejects_redirect(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)

        with patch("xiaozhi_drawing.image_url_validation.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)

            async def redirect_get(url, **kwargs):
                req = httpx.Request("GET", url if isinstance(url, str) else str(url))
                return httpx.Response(302, headers={"location": "http://evil.internal/x"}, request=req)

            mock_instance.get = redirect_get
            MockClient.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_pinned("https://api.telegram.org/image.png")

    @pytest.mark.asyncio
    async def test_rejects_private_ip_resolution(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_private)
        with pytest.raises(ValueError, match="blocked"):
            await fetch_pinned("https://api.telegram.org/image.png")
