"""Validate that the production nginx config exposes /health/ready correctly."""

from __future__ import annotations

from pathlib import Path

import pytest

_SOURCE_CONF = Path("_nginx_chat_temp.conf")
_VPS_CONF = Path("infra/vps/nginx/chat.donglicao.com.conf")


def _extract_location_block(text: str, location: str) -> str | None:
    """Naive parser: return the body of a nginx location block."""
    marker = f"location = {location} "
    start = text.find(marker)
    if start == -1:
        return None
    brace_start = text.find("{", start)
    if brace_start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[brace_start:], start=brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start : i + 1]
    return None


@pytest.mark.parametrize("conf_path", [_SOURCE_CONF, _VPS_CONF], ids=["source", "vps_snapshot"])
def test_health_ready_location_exists(conf_path: Path):
    text = conf_path.read_text(encoding="utf-8")
    block = _extract_location_block(text, "/health/ready")
    assert block is not None, f"{conf_path} missing /health/ready location"


@pytest.mark.parametrize("conf_path", [_SOURCE_CONF, _VPS_CONF], ids=["source", "vps_snapshot"])
def test_health_ready_proxies_to_app(conf_path: Path):
    text = conf_path.read_text(encoding="utf-8")
    block = _extract_location_block(text, "/health/ready")
    assert "proxy_pass http://127.0.0.1:8080" in block


@pytest.mark.parametrize("conf_path", [_SOURCE_CONF, _VPS_CONF], ids=["source", "vps_snapshot"])
def test_health_ready_has_fast_timeouts(conf_path: Path):
    text = conf_path.read_text(encoding="utf-8")
    block = _extract_location_block(text, "/health/ready")
    assert "proxy_connect_timeout 5s" in block
    assert "proxy_read_timeout 10s" in block
    assert "proxy_send_timeout 10s" in block


@pytest.mark.parametrize("conf_path", [_SOURCE_CONF, _VPS_CONF], ids=["source", "vps_snapshot"])
def test_health_ready_does_not_buffer(conf_path: Path):
    text = conf_path.read_text(encoding="utf-8")
    block = _extract_location_block(text, "/health/ready")
    assert "proxy_buffering off" in block
