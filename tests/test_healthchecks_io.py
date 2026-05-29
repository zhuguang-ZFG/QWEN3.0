"""Tests for healthchecks_io provisioning helpers."""

from __future__ import annotations

import healthchecks_io as hio


def test_slug_ping_url():
    assert hio.slug_ping_url("abc-key", "lima-vps-router") == (
        "https://hc-ping.com/abc-key/lima-vps-router"
    )


def test_provision_slug_check_success():
    class FakeResponse:
        status_code = 200
        text = "OK"

    class FakeClient:
        def get(self, url):
            assert "create=1" in url
            return FakeResponse()

        def close(self):
            return None

    ok, detail = hio.provision_slug_check("abc-key", "lima-vps-router", client=FakeClient())
    assert ok is True
    assert "status=200" in detail


def test_ensure_check_via_api_reuses_existing():
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "checks": [
                    {"name": "Lima Vps Router", "ping_url": "https://hc-ping.com/uuid-1"},
                ],
            }

    class FakeClient:
        def get(self, url, headers=None):
            assert "/checks/" in url
            return FakeResponse()

        def post(self, url, headers=None, json=None):
            raise AssertionError("should not create when exists")

        def close(self):
            return None

    ping, detail = hio.ensure_check_via_api("key", "Lima Vps Router", client=FakeClient())
    assert ping == "https://hc-ping.com/uuid-1"
    assert "reused" in detail


def test_resolve_explicit_ping_url():
    url, detail = hio.resolve_vps_router_ping_url(
        ping_url="https://hc-ping.com/example-uuid",
    )
    assert url == "https://hc-ping.com/example-uuid"
    assert detail == "explicit ping url"
