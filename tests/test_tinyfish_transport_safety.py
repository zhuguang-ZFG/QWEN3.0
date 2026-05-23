from search_gateway.tinyfish_transport import _is_safe_url


def test_tinyfish_transport_reuses_strict_public_url_safety():
    assert _is_safe_url("https://docs.python.org/3/library/asyncio.html") is True
    assert _is_safe_url("http://[::1]:8080/admin") is False
    assert _is_safe_url("http://0x7f000001/admin") is False
    assert _is_safe_url("http://2130706433/admin") is False
    assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False
