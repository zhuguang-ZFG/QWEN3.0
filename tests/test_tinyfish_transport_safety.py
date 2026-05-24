import socket

import pytest

import search_gateway.safety as safety
from search_gateway.tinyfish_transport import _is_safe_url


@pytest.fixture(autouse=True)
def deterministic_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        normalized = host.lower().rstrip(".")
        if normalized == "localtest.me":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        if normalized == "docs.python.org":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.243", port))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(safety.socket, "getaddrinfo", fake_getaddrinfo)


def test_tinyfish_transport_reuses_strict_public_url_safety():
    assert _is_safe_url("https://docs.python.org/3/library/asyncio.html") is True
    assert _is_safe_url("http://[::1]:8080/admin") is False
    assert _is_safe_url("http://0x7f000001/admin") is False
    assert _is_safe_url("http://2130706433/admin") is False
    assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert _is_safe_url("http://localhost./admin") is False
    assert _is_safe_url("http://localtest.me/admin") is False
