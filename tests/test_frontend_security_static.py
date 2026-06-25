"""Static security checks for public chat pages and firmware defaults."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_public_chat_has_content_security_policy() -> None:
    text = (ROOT / "chat-web/index.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in text
    assert "upgrade-insecure-requests" in text


def test_public_chat_code_blocks_escape_html() -> None:
    import re

    text = (ROOT / "chat-web/chat-messages.js").read_text(encoding="utf-8")
    # Code captured from triple backticks must be HTML-escaped before insertion.
    assert re.search(r"<code[^>]*>\$\{escapeHtml\(code\)\}</code>", text), "code block must escape HTML"
    assert "onclick=\"copyCode" not in text


def test_public_chat_renderer_does_not_restore_unescaped_image_attributes() -> None:
    """Markdown image support must not reintroduce raw user/model strings into innerHTML."""
    for rel in ("donglicao-site/chat.html", "chat-web/index.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "imgs.push({alt,url})" not in text
        assert "'<img src=\"'+img.url+'\" alt=\"'+img.alt" not in text


def test_lima_direct_firmware_defaults_to_secure_websocket() -> None:
    text = (ROOT / "esp32S_XYZ/firmware/u8-xiaozhi/main/protocols/websocket_protocol.cc").read_text(encoding="utf-8")
    assert 'url = "wss://chat.donglicao.com/device/v1/ws";' in text
    assert 'url = "ws://chat.donglicao.com/device/v1/ws";' not in text


def test_firmware_websocket_protocol_is_lima_only() -> None:
    text = (ROOT / "esp32S_XYZ/firmware/u8-xiaozhi/main/protocols/websocket_protocol.cc").read_text(encoding="utf-8")
    assert "CONFIG_LIMA_DIRECT_MODE" not in text
    assert "Original xiaozhi-server protocol" not in text
    assert "Original xiaozhi-server hello parsing" not in text
    assert 'cJSON_AddStringToObject(root, "protocol", LIMA_PROTOCOL_VERSION);' in text
    assert 'strcmp(type->valuestring, "hello_ack") == 0' in text
