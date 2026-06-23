"""Tests for routes/admin_backends.py — backend URL safety helpers."""

import socket
from unittest.mock import patch

from routes.admin_backends import _is_safe_backend_url, _resolve_vendor


    def test_unknown(self):
        assert _resolve_vendor("https://example.com") == "未知"


class TestIsSafeBackendUrl:
    def test_https_public_domain(self):
        with patch("routes.admin_backends.socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", None))]
            assert _is_safe_backend_url("https://api.example.com/v1") is True

    def test_http_rejected(self):
        assert _is_safe_backend_url("http://api.example.com/v1") is False

    def test_localhost_rejected(self):
        assert _is_safe_backend_url("https://localhost:8080") is False

    def test_private_ip_rejected(self):
        assert _is_safe_backend_url("https://192.168.1.1") is False

    def test_loopback_rejected(self):
        assert _is_safe_backend_url("https://127.0.0.1") is False

    def test_file_scheme_rejected(self):
        assert _is_safe_backend_url("file:///etc/passwd") is False

    def test_dns_failure_rejected(self):
        with patch("routes.admin_backends.socket.getaddrinfo", side_effect=socket.gaierror):
            assert _is_safe_backend_url("https://bad-domain.local") is False
