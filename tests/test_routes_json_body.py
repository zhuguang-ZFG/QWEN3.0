"""Tests for routes/json_body.py helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from routes.json_body import invalid_json_response, read_json_object


class TestInvalidJsonResponse:
    def test_openai_error_shape(self):
        response = invalid_json_response("bad", openai_error=True)
        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"]["message"] == "bad"
        assert body["error"]["type"] == "invalid_request_error"

    def test_plain_error_shape(self):
        response = invalid_json_response("bad", openai_error=False)
        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"] == "bad"


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
        request.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        result = await read_json_object(request)
        assert result.status_code == 400
        assert json.loads(result.body)["error"] == "valid JSON body required"

    @pytest.mark.asyncio
    async def test_non_object_body(self):
        request = AsyncMock()
        request.json.return_value = [1, 2]
        result = await read_json_object(request)
        assert result.status_code == 400
        assert json.loads(result.body)["error"] == "JSON object body required"

    @pytest.mark.asyncio
    async def test_openai_error_format(self):
        request = AsyncMock()
        request.json.return_value = "not an object"
        result = await read_json_object(request, openai_error=True)
        body = json.loads(result.body)
        assert body["error"]["type"] == "invalid_request_error"
