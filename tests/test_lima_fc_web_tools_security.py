import pytest

from lima_fc_tools import web_tools


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "http://localhost:8080/health",
        "http://127.0.0.1:8080/health",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_rejects_non_public_fetch_targets(url):
    allowed, reason = web_tools._validate_public_http_url(url)

    assert allowed is False
    assert reason


def test_accepts_public_https_url():
    allowed, reason = web_tools._validate_public_http_url("https://example.com/docs")

    assert allowed is True
    assert reason == ""
