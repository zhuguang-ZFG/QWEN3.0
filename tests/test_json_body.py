"""Tests for routes/json_body.py — JSON parsing helpers."""

import pytest
from unittest.mock import AsyncMock

from routes.json_body import invalid_json_response, read_json_object


class TestInvalidJsonResponse:
    def test_plain(self):
        resp = invalid_json_response("bad")
        assert resp.status_code == 400
        assert resp.body == b'{"error":"bad"}'

    def test_openai(self):
        resp = invalid_json_response("bad", openai_error=True)
        assert resp.status_code == 400
        assert b"invalid_request_error" in resp.body


class TestReadJsonObject:
    @pytest.mark.asyncio
    async def test_valid_dict(self):
        request = AsyncMock()
        request.json.return_value = {"a": 1}
        result = await read_json_object(request)
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        request = AsyncMock()
        request.json.side_effect = ValueError("bad json")
        result = await read_json_object(request)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_array_body(self):
        request = AsyncMock()
        request.json.return_value = [1, 2]
        result = await read_json_object(request)
        assert result.status_code == 400
