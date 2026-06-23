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

    def test_missing(self):
        assert str_field({}, "a") == ""

    def test_whitespace_only_ignored(self):
        assert str_field({"a": "  "}, "a", "b") == ""


class TestQueryInt:
    def test_valid(self):
        assert query_int("10", 5, 0, 100) == 10

    def test_default_on_missing(self):
        assert query_int(None, 5, 0, 100) == 5

    def test_clamped_to_minimum(self):
        assert query_int("-5", 5, 0, 100) == 0

    def test_clamped_to_maximum(self):
        assert query_int("999", 5, 0, 100) == 100


class TestExpiresAt:
    def test_format(self):
        assert expires_at(3600).endswith("Z")


class TestLoadsJson:
    def test_valid(self):
        assert loads_json('{"a":1}') == {"a": 1}

    def test_invalid(self):
        assert loads_json("not json") == {}

    def test_non_string(self):
        assert loads_json(123) == {}
