"""Tests for JDCloud Worker proxy backends (Phase 2)."""

import backends_registry
from http_request_builder.headers import _select_key


POLLINATIONS_BACKENDS = {
    "jdcloud_pollinations_openai": {
        "url": "http://100.85.114.65:8700/proxy/pollinations",
        "model": "openai",
        "key_env_var": "JDCLOUD_WORKER_TOKEN",
        "fmt": "openai",
        "timeout": 45,
    },
    "jdcloud_pollinations_deepseek": {
        "url": "http://100.85.114.65:8700/proxy/pollinations",
        "model": "deepseek",
        "key_env_var": "JDCLOUD_WORKER_TOKEN",
        "fmt": "openai",
        "timeout": 45,
    },
}


def test_jdcloud_pollinations_backends_registered():
    for name in POLLINATIONS_BACKENDS:
        assert name in backends_registry.BACKENDS, f"{name} not found in BACKENDS"


def test_jdcloud_pollinations_backend_config():
    for name, expected in POLLINATIONS_BACKENDS.items():
        cfg = backends_registry.BACKENDS[name]
        for field, value in expected.items():
            assert cfg.get(field) == value, f"{name}.{field} = {cfg.get(field)!r}, expected {value!r}"


def test_jdcloud_pollinations_backend_headers():
    for name in POLLINATIONS_BACKENDS:
        headers = backends_registry.BACKENDS[name].get("headers", {})
        assert headers.get("User-Agent") == "LiMa-JDCloud-Proxy/1.0"


def test_jdcloud_pollinations_select_key_uses_env_var(monkeypatch):
    monkeypatch.setenv("JDCLOUD_WORKER_TOKEN", "jdcloud-shared-token")
    for name in POLLINATIONS_BACKENDS:
        cfg = backends_registry.BACKENDS[name]
        key, _provider = _select_key(name, cfg)
        assert key == "jdcloud-shared-token", f"{name} did not read JDCLOUD_WORKER_TOKEN"


def test_jdcloud_pollinations_select_key_empty_without_env_var(monkeypatch):
    monkeypatch.delenv("JDCLOUD_WORKER_TOKEN", raising=False)
    for name in POLLINATIONS_BACKENDS:
        cfg = backends_registry.BACKENDS[name]
        key, _provider = _select_key(name, cfg)
        assert key == "", f"{name} should return empty key when env var is unset"


def test_jdcloud_pollinations_in_routing_pools():
    from router_v3 import POOLS

    assert "jdcloud_pollinations_deepseek" in POOLS["chat"]["floor"]
    assert "jdcloud_pollinations_openai" in POOLS["chat_fast"]["floor"]


def test_no_free_openai_next_backends_registered():
    """free_openai_next was a scaffold provider; main must not ship dead routes."""
    assert "jdcloud_free_openai_next_gpt4" not in backends_registry.BACKENDS
    assert "jdcloud_free_openai_next_claude" not in backends_registry.BACKENDS
