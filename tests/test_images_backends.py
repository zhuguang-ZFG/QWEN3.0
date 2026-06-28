"""Tests for routes/images_backends.py helpers."""

from __future__ import annotations

from routes import images_backends as backends


def test_map_to_openai_image_size():
    assert backends._map_to_openai_image_size("1024x1024") == "1024x1024"
    assert backends._map_to_openai_image_size("1792x1024") == "1792x1024"
    assert backends._map_to_openai_image_size("1024x1792") == "1024x1792"
    assert backends._map_to_openai_image_size("512x512") == "1024x1024"
    assert backends._map_to_openai_image_size("invalid") == "1024x1024"


def test_extract_image_url_finds_first_url():
    content = "Here is the image: https://example.com/image.png enjoy!"
    assert backends._extract_image_url(content) == "https://example.com/image.png"


def test_extract_openai_image_url_prefers_url():
    assert backends._extract_openai_image_url({"url": "https://x.png"}) == "https://x.png"


def test_extract_openai_image_url_falls_back_to_b64():
    assert backends._extract_openai_image_url({"b64_json": "aGVsbG8="}) == "data:image/png;base64,aGVsbG8="
