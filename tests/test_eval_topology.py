"""Tests for eval topology routing (P2-25)."""

from __future__ import annotations

import json

import eval_topology


def test_needs_via_router_when_local_port_closed(monkeypatch):
    monkeypatch.setenv("LIMA_EVAL_TOPOLOGY", "1")
    monkeypatch.setenv("LIMA_EVAL_VIA_ROUTER_URL", "http://127.0.0.1:8088")
    monkeypatch.setattr(eval_topology, "backend_available", lambda _name: False)
    assert eval_topology.needs_via_router("scnet_large_ds_flash") is True
    assert eval_topology.needs_via_router("scnet_qwen30b") is False


def test_needs_via_router_false_when_local_available(monkeypatch):
    monkeypatch.setenv("LIMA_EVAL_VIA_ROUTER_URL", "http://127.0.0.1:8088")
    monkeypatch.setattr(eval_topology, "backend_available", lambda _name: True)
    assert eval_topology.needs_via_router("scnet_large_ds_flash") is False


def test_call_via_router_posts_internal_endpoint(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    captured: dict = {}

    class FakeResp:
        def read(self, _size=-1):
            return json.dumps({"ok": True, "answer": "def add(a,b): return a+b"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode())
        return FakeResp()

    monkeypatch.setattr(eval_topology.urllib.request, "urlopen", fake_urlopen)
    answer = eval_topology.call_via_router(
        "scnet_large_ds_flash",
        [{"role": "user", "content": "fix add"}],
        512,
        router_url="http://127.0.0.1:8088",
    )
    assert "def add" in answer
    assert captured["url"].endswith("/internal/v1/eval/call")
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["backend"] == "scnet_large_ds_flash"
