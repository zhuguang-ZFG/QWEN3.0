"""Tests for device_gateway.device_write_handler — text-to-path writing."""

import pytest
from device_gateway.device_write_handler import handle_device_write


@pytest.mark.asyncio
async def test_handle_device_write_basic():
    """Test basic write request."""
    result = await handle_device_write("Hello", device_id="dev-1")
    assert result["status"] == "success"
    assert isinstance(result["path_data"], list)
    assert len(result["path_data"]) > 0
    assert result["preview_svg"] != ""
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["model"] == "deterministic"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_handle_device_write_with_font_style():
    """Test write request with different font styles."""
    for style in ["default", "handwriting", "calligraphy"]:
        result = await handle_device_write("Test", font_style=style)
        assert result["status"] == "success"
        assert isinstance(result["path_data"], list)
        assert len(result["path_data"]) > 0


@pytest.mark.asyncio
async def test_handle_device_write_with_size():
    """Test write request with different sizes."""
    for size in ["small", "medium", "large"]:
        result = await handle_device_write("Test", size=size)
        assert result["status"] == "success"
        assert isinstance(result["path_data"], list)
        assert len(result["path_data"]) > 0


@pytest.mark.asyncio
async def test_handle_device_write_empty_text():
    """Test write request with empty text."""
    result = await handle_device_write("")
    assert result["status"] == "success"
    assert isinstance(result["path_data"], list)
    assert len(result["path_data"]) == 0


@pytest.mark.asyncio
async def test_handle_device_write_special_chars():
    """Test write request with special characters."""
    result = await handle_device_write("Hello! @#$%")
    assert result["status"] == "success"
    assert isinstance(result["path_data"], list)
    assert len(result["path_data"]) > 0


@pytest.mark.asyncio
async def test_handle_device_write_preview_svg():
    """Test that preview SVG is generated."""
    result = await handle_device_write("Test")
    assert result["status"] == "success"
    assert "<svg" in result["preview_svg"]
    assert "viewBox" in result["preview_svg"]
