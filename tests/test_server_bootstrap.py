"""Tests for server_bootstrap.py helpers."""

from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError


import server_bootstrap as sb


class TestLastResortCall:
    def _cloudflare_mock(self, configured: bool = True):
        cf = MagicMock()
        cf.configured = configured
        cf.chat_url.return_value = "https://fake.cloudflare/ai"
        cf.token = "fake-token"
        return cf

    def test_last_resort_returns_fallback_when_not_configured(self):
        with patch.object(sb, "CLOUDFLARE", self._cloudflare_mock(configured=False)):
            result = sb.last_resort_call([{"role": "user", "content": "hi"}])
        assert result == sb.LAST_RESORT_FALLBACK_MESSAGE

    def test_last_resort_returns_content_on_success(self):
        cf = self._cloudflare_mock()
        with patch.object(sb, "CLOUDFLARE", cf):
            with patch("server_bootstrap.urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = json.dumps(
                    {"choices": [{"message": {"content": "cloudflare says hi"}}]}
                ).encode()
                mock_urlopen.return_value = mock_response
                result = sb.last_resort_call([{"role": "user", "content": "hi"}])
        assert result == "cloudflare says hi"

    def test_last_resort_returns_fallback_and_logs_on_failure(self, caplog):
        cf = self._cloudflare_mock()
        with patch.object(sb, "CLOUDFLARE", cf):
            with patch(
                "server_bootstrap.urllib.request.urlopen",
                side_effect=HTTPError(
                    "https://fake.cloudflare/ai",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "boom",
                    {},
                    None,
                ),
            ):
                with caplog.at_level("WARNING"):
                    result = sb.last_resort_call([{"role": "user", "content": "hi"}])
        assert result == sb.LAST_RESORT_FALLBACK_MESSAGE
        assert any("Cloudflare fallback failed" in rec.message for rec in caplog.records)
