from starlette.requests import Request

from routes.request_tracking import client_ip


def _request(client_host: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "client": (client_host, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_client_ip_ignores_xff_from_untrusted_direct_peer() -> None:
    request = _request("198.51.100.9", [(b"x-forwarded-for", b"203.0.113.1")])

    assert client_ip(request) == "198.51.100.9"


def test_client_ip_uses_leftmost_forwarded_client_from_trusted_proxy() -> None:
    request = _request("127.0.0.1", [(b"x-forwarded-for", b"203.0.113.44, 198.51.100.77")])

    assert client_ip(request) == "203.0.113.44"


def test_client_ip_prefers_cf_connecting_ip_from_trusted_proxy() -> None:
    request = _request(
        "127.0.0.1",
        [
            (b"cf-connecting-ip", b"203.0.113.10"),
            (b"x-forwarded-for", b"203.0.113.10, 172.71.1.1"),
        ],
    )

    assert client_ip(request) == "203.0.113.10"


def test_client_ip_uses_x_real_ip_when_cf_header_missing() -> None:
    request = _request(
        "127.0.0.1",
        [
            (b"x-real-ip", b"203.0.113.11"),
            (b"x-forwarded-for", b"172.71.1.1, 203.0.113.11"),
        ],
    )

    assert client_ip(request) == "203.0.113.11"
