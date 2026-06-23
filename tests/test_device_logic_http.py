"""Tests for device_logic/http.py — HTTP helpers."""

from unittest.mock import AsyncMock

import pytest

from device_logic.http import ok, err, read_body, now, new_id, str_field, query_int, expires_at, loads_json


class TestOk:
    def test_ok_response(self):
        response = ok({"id": 1})
        assert response.status_code == 200
        assert response.body == b'{"code":0,"data":{"id":1}}'


class TestErr:
    def test_err_response(self):
        response = err(1, "bad request")
        assert response.status_code == 400
        assert b"bad request" in response.body


class TestReadBody:
    @pytest.mark.asyncio
    async def test_valid_dict(self):
        request = AsyncMock()
        request.json.return_value = {"a": 1}
        result = await read_body(request)
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        request = AsyncMock()
        request.json.side_effect = ValueError("bad")
        result = await read_body(request)
        assert result.status_code == 400


class TestNow:
    def test_format(self):
        assert now().endswith("Z")


class TestNewId:
    def test_returns_uuid(self):
        assert len(new_id()) == 36


class TestStrField:
    def test_first_present(self):
        assert str_field({"a": "x", "b": "y"}, "a", "b") == "x"

    def test_fallback(self):
        assert str_field({"b": "y"}, "a", "b") == "y"

    def test_default(self):
        assert str_field({}, "a", default="z") == "z"


class TestQueryInt:
    def test_valid(self):
        assert query_int({"limit": "10"}, "limit", 5) == 10

    def test_default(self):
        assert query_int({}, "limit", 5) == 5


class TestExpiresAt:
    def test_format(self):
        assert expires_at(3600).endswith("Z")


class TestLoadsJson:
    def test_valid(self):
        assert loads_json('{"a":1}') == {"a": 1}

    def test_invalid(self):
        assert loads_json("not json") is None
