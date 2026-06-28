"""Tests for routes/images_pollinations.py."""

from __future__ import annotations

import pytest

from routes import images_pollinations as pollinations


@pytest.fixture(autouse=True)
def _disable_translation(monkeypatch):
    monkeypatch.setattr(pollinations, "_PROMPT_TRANSLATE_ENABLED", False)


def test_build_pollinations_url():
    url = pollinations.build_pollinations_url("hello world", "512x256")
    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "width=512" in url
    assert "height=256" in url
    assert "nologo=true" in url


def test_build_pollinations_url_with_options():
    url = pollinations.build_pollinations_url(
        "hello",
        "512x256",
        {
            "seed": 42,
            "negative_prompt": "blur",
            "enhance": True,
            "safe": True,
            "private": True,
            "model": "flux",
        },
    )
    assert "seed=42" in url
    assert "negative=blur" in url
    assert "enhance=true" in url
    assert "safe=true" in url
    assert "private=true" in url
    assert "model=flux" in url
    assert "nologo=true" in url


def test_build_pollinations_url_ignores_default_model():
    url = pollinations.build_pollinations_url("hello", "512x256", {"model": "lima-image"})
    assert "model=" not in url


def test_build_variant_is_deterministic():
    opts = {"seed": 1, "model": "flux"}
    assert pollinations.build_variant(opts) == pollinations.build_variant({"model": "flux", "seed": 1})
