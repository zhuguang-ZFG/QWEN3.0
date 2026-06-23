"""Tests for routes/ws_voiceprint_helpers.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes import ws_voiceprint_helpers as vp


@pytest.fixture
def websocket():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_handle_voiceprint_sample_success(websocket):
    validated = {
        "member_id": "member-1",
        "voiceprint_id": "vp-1",
        "sample_index": 2,
        "audio_data": "data",
        "format": "wav",
    }
    with patch("routes.ws_voiceprint_helpers.shadow_store") as mock_shadow, patch(
        "session_memory.store_voiceprint.upsert_voiceprint_sample"
    ) as mock_upsert, patch(
        "routes.ws_voiceprint_helpers.build_voiceprint_sample_ack",
        return_value={"type": "voiceprint_sample_ack"},
    ) as mock_ack, patch(
        "routes.device_voice_ws_helpers._extract_and_store_voiceprint_embedding"
    ) as mock_extract:
        mock_shadow.validate_voiceprint_sample.return_value = validated
        await vp.handle_voiceprint_sample(websocket, "dev-1", {"raw": "msg"}, "req-1")

    mock_shadow.validate_voiceprint_sample.assert_called_once_with({"raw": "msg"})
    mock_upsert.assert_called_once_with(
        voiceprint_id="vp-1",
        member_id="member-1",
        device_id="dev-1",
        sample_index=2,
        audio_data="data",
        format="wav",
    )
    mock_ack.assert_called_once_with(
        device_id="dev-1",
        voiceprint_id="vp-1",
        sample_index=2,
        request_id="req-1",
    )
    websocket.send_json.assert_awaited_once_with({"type": "voiceprint_sample_ack"})
    mock_extract.assert_awaited_once_with(validated, "vp-1", "member-1", "dev-1")
    mock_shadow.update_voiceprint_sample.assert_called_once_with({"raw": "msg"})


@pytest.mark.asyncio
async def test_handle_voiceprint_sample_import_error_fallback(websocket):
    validated = {"voiceprint_id": "vp-1", "sample_index": 0}
    with patch("routes.ws_voiceprint_helpers.shadow_store") as mock_shadow, patch(
        "session_memory.store_voiceprint.upsert_voiceprint_sample",
        side_effect=ImportError("no db"),
    ), patch(
        "routes.ws_voiceprint_helpers.ack_frame",
        return_value={"type": "fallback_ack"},
    ) as mock_ack:
        mock_shadow.validate_voiceprint_sample.return_value = validated
        await vp.handle_voiceprint_sample(websocket, "dev-1", {"raw": "msg"}, "req-1")

    mock_ack.assert_called_once_with(
        "voiceprint_sample_ack",
        "dev-1",
        voiceprint_id="vp-1",
        sample_index=0,
        request_id="req-1",
    )
    websocket.send_json.assert_awaited_once_with({"type": "fallback_ack"})
