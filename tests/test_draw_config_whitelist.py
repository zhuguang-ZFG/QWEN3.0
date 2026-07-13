"""Tests for caller_model whitelist in resolve_draw_model."""

from __future__ import annotations

from device_gateway.device_draw_config import resolve_draw_model, ALLOWED_WANX_MODELS


def test_whitelisted_model_accepted():
    """caller_model in whitelist → returned."""
    model = resolve_draw_model("dashscope_wanx", "wanx2.1-t2i-turbo")
    assert model == "wanx2.1-t2i-turbo"


def test_unknown_model_rejected():
    """caller_model not in whitelist → fallback to default."""
    model = resolve_draw_model("dashscope_wanx", "wanx2.1-expensive-hack")
    assert model == "wanx2.1-t2i-turbo"  # default, not the injected one


def test_empty_caller_model():
    """Empty caller_model → default."""
    model = resolve_draw_model("dashscope_wanx", "")
    assert model == "wanx2.1-t2i-turbo"


def test_non_wanx_backend_unaffected():
    """Non-wanx backend ignores caller_model."""
    model = resolve_draw_model("dashscope_flux", "wanx2.1-t2i-turbo")
    assert model == "flux-schnell"


def test_whitelist_contains_known_models():
    """Whitelist includes all DRAW_BACKEND_MODELS values."""
    assert "wanx2.1-t2i-turbo" in ALLOWED_WANX_MODELS
    assert "flux-schnell" in ALLOWED_WANX_MODELS
