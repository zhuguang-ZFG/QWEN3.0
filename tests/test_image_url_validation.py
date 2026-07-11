"""Tests for device_gateway.image_url_validation."""

from __future__ import annotations

import pytest

from device_gateway import image_url_validation as iv


def test_reject_non_allowlisted_host() -> None:
    url, err = iv.validate_image_url("https://example.com/img.png")
    assert url is None
    assert err and "not allowed" in err


def test_reject_literal_private_ip() -> None:
    url, err = iv.validate_image_url("https://127.0.0.1/img.png")
    assert url is None
    assert err and ("blocked" in err.lower() or "private" in err.lower())


def test_allow_telegram_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iv, "_resolve_hostname", lambda _host: ["149.154.167.220"])
    url, err = iv.validate_image_url("https://api.telegram.org/file/bot123/img.png")
    assert err is None
    assert url is not None


def test_allow_verify_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iv, "_resolve_hostname", lambda _host: ["8.8.8.8"])
    url, err = iv.validate_image_url("https://chat.donglicao.com/device/v1/app/gallery/x/file")
    assert err is None
    assert url is not None
